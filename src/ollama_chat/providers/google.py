# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The Google (Gemini) provider adapter - the Gemini generateContent API. Converts between the
internal message/chunk format (the Ollama chat API format) and the Gemini contents format,
including the server-sent events streaming protocol. The API key travels as the "key" query
parameter.
"""

import base64
import re

from .base import ProviderError
from .defaults import provider_base_url
from .http import HTTPProvider, _error_text, _response_json
from .stream import iter_sse_json


# The model-name heuristic for Gemini's thinking models - the 2.5 generation reasons by default
_RE_THINKING_MODEL = re.compile(r'gemini-2\.5|thinking', re.IGNORECASE)


# The Google Gemini provider
class GoogleProvider(HTTPProvider):
    __slots__ = ()


    supports_tools = True


    # The API key travels as a query parameter, not a header
    def _base_headers(self):
        return {'Content-Type': 'application/json'}


    # A provider API URL, with the API key appended as the "key" query parameter
    def _api_url(self, path):
        base_url = (provider_base_url(self.config) or '').rstrip('/')
        if not base_url:
            raise ProviderError(
                'BadBaseUrl',
                f'The provider "{self.provider_name}" has no base URL - set one in settings.'
            )
        separator = '&' if '?' in path else '?'
        return f'{base_url}/{path}{separator}key={self._api_key()}'


    def list_models(self):
        response = self._request('GET', self._api_url('models'))
        try:
            if response.status != 200:
                self._raise_for_status(response)
            body = _response_json(response)
        finally:
            response.close()
        models = []
        for model in (body.get('models') or []) if isinstance(body, dict) else []:
            if not isinstance(model, dict):
                continue
            name = model.get('name') or ''
            model_id = name[len('models/'):] if name.startswith('models/') else name
            if not model_id:
                continue
            models.append({'id': model_id, 'name': model.get('displayName') or model_id})
        return models


    def model_capabilities(self, model):
        return {
            'tools': True,
            'vision': 'gemini' in model.lower(),
            'thinking': bool(_RE_THINKING_MODEL.search(model))
        }


    def chat_stream(self, model, messages, think=None, tools=None, num_ctx=None, capabilities=None):
        system_text, contents = self._convert_messages(messages)
        body = {'contents': contents}
        if system_text:
            body['systemInstruction'] = {'parts': [{'text': system_text}]}
        if tools:
            body['tools'] = [{'functionDeclarations': self._convert_tools(tools)}]
        if think:
            body['generationConfig'] = {'thinkingConfig': {'thinkingBudget': -1}} # dynamic budget

        # Start the streaming chat request (SSE)
        url = self._api_url(f'models/{model}:streamGenerateContent?alt=sse')
        response = self._request('POST', url, body)
        try:
            if response.status != 200:
                self._raise_for_status(response, model)

            # Stream the SSE events, converting each to an internal-format chunk. Function
            # calls arrive complete, but are yielded as one final chunk like the other
            # providers.
            tool_calls = []
            done = False
            for event in iter_sse_json(response):
                if not isinstance(event, dict):
                    continue
                if 'error' in event:
                    raise self._stream_error(event['error'], model)
                for candidate in event.get('candidates') or []:
                    if not isinstance(candidate, dict):
                        continue
                    content = candidate.get('content') or {}
                    for part in content.get('parts') or []:
                        if not isinstance(part, dict):
                            continue
                        if part.get('thought'):
                            text = part.get('text')
                            if text:
                                yield {'message': {'thinking': text}}
                        elif 'text' in part and part['text']:
                            yield {'message': {'content': part['text']}}
                        elif 'functionCall' in part:
                            function_call = part['functionCall'] or {}
                            tool_calls.append({
                                'function': {
                                    'name': function_call.get('name') or '',
                                    'arguments': function_call.get('args') or {}
                                }
                            })
                    if candidate.get('finishReason'):
                        done = True

            if done or tool_calls:
                yield {
                    'message': {'tool_calls': tool_calls} if tool_calls else {},
                    'done': True
                }
        finally:
            response.close()


    def test_connection(self):
        models = self.list_models()
        return f'{self.provider_name} is available ({len(models)} models)'


    # Map a streamed error payload to a ProviderError with the same user-facing mapping as HTTP
    # statuses
    def _stream_error(self, error, model):
        code = error.get('code') if isinstance(error, dict) else None
        detail = _error_text(error)
        detail_lower = detail.lower()
        if code in (401, 403) or (code == 400 and 'api key' in detail_lower):
            return ProviderError(
                'InvalidApiKey',
                f'{self.provider_name} rejected the API key (HTTP {code}). '
                'Check the API key in settings.' + (f' - {detail}' if detail else '')
            )
        if code == 429:
            return ProviderError(
                'RateLimited',
                f'{self.provider_name} rate limit reached (HTTP 429). Try again later.'
                + (f' - {detail}' if detail else '')
            )
        if code == 404 or (model is not None and 'model' in detail_lower):
            return ProviderError(
                'UnknownModel',
                f'The model "{model}" was not found on {self.provider_name}. '
                'Refresh the model list and select another model.'
            )
        return ProviderError('ProviderError', f'{self.provider_name}: {detail or "stream error"}')


    # Convert internal-format messages to the Gemini (systemInstruction, contents) pair.
    # Assistant messages use the "model" role; consecutive tool results are merged into one
    # user turn.
    def _convert_messages(self, messages):
        system_parts = []
        contents = []
        tool_response_parts = None # the functionResponse parts of the last turn, if any
        for message in messages:
            role = message.get('role')
            content = message.get('content') or ''
            if role == 'system':
                system_parts.append(content)
            elif role == 'tool':
                part = {
                    'functionResponse': {
                        'name': message.get('tool_name') or '',
                        'response': {'content': content}
                    }
                }
                if tool_response_parts is None:
                    contents.append({'role': 'user', 'parts': [part]})
                    tool_response_parts = contents[-1]['parts']
                else:
                    tool_response_parts.append(part)
            elif role == 'assistant':
                tool_response_parts = None
                parts = []
                if content:
                    parts.append({'text': content})
                for tool_call in message.get('tool_calls') or []:
                    function = tool_call.get('function') or {}
                    parts.append({
                        'functionCall': {
                            'name': function.get('name') or '',
                            'args': function.get('arguments') or {}
                        }
                    })
                contents.append({'role': 'model', 'parts': parts or [{'text': ''}]})
            else: # user
                tool_response_parts = None
                parts = []
                if content:
                    parts.append({'text': content})
                for image_data in message.get('images') or []:
                    parts.append({
                        'inlineData': {
                            'mimeType': _image_mime_type(image_data),
                            'data': image_data
                        }
                    })
                contents.append({'role': 'user', 'parts': parts or [{'text': ''}]})
        return '\n\n'.join(system_parts), contents


    # Convert internal OpenAI-format tool definitions to Gemini function declarations
    def _convert_tools(self, tools):
        declarations = []
        for tool in tools or []:
            function = tool.get('function') or tool
            declarations.append({
                'name': function.get('name') or '',
                'description': function.get('description') or '',
                'parameters': function.get('parameters') or function.get('input_schema') or {}
            })
        return declarations


# Sniff a base64 image's MIME type (JPEG starts FF D8, everything else is treated as PNG)
def _image_mime_type(image_data):
    try:
        first_bytes = base64.b64decode(image_data[:16] + '===')
    except (ValueError, TypeError):
        return 'image/png'
    return 'image/jpeg' if first_bytes[:2] == b'\xff\xd8' else 'image/png'
