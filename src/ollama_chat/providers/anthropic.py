# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The Anthropic provider adapter - the Claude Messages API. Converts between the internal
message/chunk format (the Ollama chat API format) and the Anthropic messages format,
including the server-sent events streaming protocol.
"""

import base64
import json

from .base import ProviderError
from .http import HTTPProvider, _error_text, _response_json
from .stream import iter_sse_json


# The Anthropic API version sent with every request
_API_VERSION = '2023-06-01'

# The default response token budget, overridable in the provider's config ("maxTokens")
_DEFAULT_MAX_TOKENS = 4096

# The thinking budget when thinking mode is enabled - half the response budget, at least 1024
_THINKING_BUDGET_MIN = 1024


# The Anthropic Claude provider
class AnthropicProvider(HTTPProvider):
    __slots__ = ()


    supports_tools = True


    def _base_headers(self):
        headers = {'Content-Type': 'application/json', 'anthropic-version': _API_VERSION}
        api_key = self._api_key()
        if api_key:
            headers['x-api-key'] = api_key
        return headers


    def list_models(self):
        response = self._request('GET', self._api_url('models'))
        try:
            if response.status != 200:
                self._raise_for_status(response)
            body = _response_json(response)
        finally:
            response.close()
        models = body.get('data') if isinstance(body, dict) else body
        return [
            {'id': model.get('id') or '', 'name': model.get('display_name') or model.get('id') or ''}
            for model in (models or [])
            if isinstance(model, dict) and model.get('id')
        ]


    def model_capabilities(self, model):
        # Every current Claude model supports vision and extended thinking - best-effort, the
        # names evolve
        return {'tools': True, 'vision': True, 'thinking': True}


    def chat_stream(self, model, messages, think=None, tools=None, num_ctx=None, capabilities=None):
        system_text, converted_messages = self._convert_messages(messages)
        max_tokens = int(self.config.get('maxTokens') or _DEFAULT_MAX_TOKENS)
        body = {
            'model': model,
            'messages': converted_messages,
            'max_tokens': max_tokens,
            'stream': True
        }
        if system_text:
            body['system'] = system_text
        if tools:
            body['tools'] = self._convert_tools(tools)
        if think:
            body['thinking'] = {
                'type': 'enabled',
                'budget_tokens': max(_THINKING_BUDGET_MIN, max_tokens // 2)
            }

        # Start the streaming chat request
        response = self._request('POST', self._api_url('messages'), body)
        try:
            if response.status != 200:
                self._raise_for_status(response, model)

            # Stream the SSE events, converting each to an internal-format chunk. Tool call
            # inputs stream in JSON pieces, so they are accumulated and yielded once complete.
            tool_call_states = {}
            done = False
            for event in iter_sse_json(response):
                if not isinstance(event, dict):
                    continue
                event_type = event.get('type')
                if event_type == 'error':
                    raise ProviderError('ProviderError', _error_text(event.get('error')))
                if event_type == 'content_block_start':
                    block = event.get('content_block') or {}
                    if block.get('type') == 'tool_use':
                        index = event.get('index') or 0
                        tool_call_states.setdefault(index, {'id': '', 'name': '', 'arguments': ''})
                        tool_call_states[index]['id'] = block.get('id') or ''
                        tool_call_states[index]['name'] = block.get('name') or ''
                elif event_type == 'content_block_delta':
                    delta = event.get('delta') or {}
                    delta_type = delta.get('type')
                    if delta_type == 'text_delta':
                        text = delta.get('text')
                        if text:
                            yield {'message': {'content': text}}
                    elif delta_type == 'thinking_delta':
                        text = delta.get('thinking')
                        if text:
                            yield {'message': {'thinking': text}}
                    elif delta_type == 'input_json_delta':
                        index = event.get('index') or 0
                        call_state = tool_call_states.setdefault(index, {'id': '', 'name': '', 'arguments': ''})
                        call_state['arguments'] += delta.get('partial_json') or ''
                elif event_type == 'message_delta':
                    if (event.get('delta') or {}).get('stop_reason') is not None:
                        done = True
                elif event_type == 'message_stop':
                    done = True

            # The final internal-format chunk, carrying the completed tool calls when the
            # model requested any
            tool_calls = _finalize_tool_calls(tool_call_states)
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


    # Convert internal-format messages to the Anthropic (system, messages) pair. The system
    # prompt is a separate Anthropic parameter; tool results travel as user content blocks and
    # consecutive tool results are merged into one user message.
    def _convert_messages(self, messages):
        system_parts = []
        converted = []
        tool_result_blocks = None # the tool_result blocks of the last user message, if any
        pending_tool_use_ids = []
        tool_call_counter = 0
        for message in messages:
            role = message.get('role')
            content = message.get('content') or ''
            if role == 'system':
                system_parts.append(content)
            elif role == 'tool':
                if pending_tool_use_ids:
                    tool_use_id = pending_tool_use_ids.pop(0)
                else: # a malformed history - keep the result referenceable anyway
                    tool_use_id = f'toolu_{tool_call_counter}'
                    tool_call_counter += 1
                block = {'type': 'tool_result', 'tool_use_id': tool_use_id, 'content': content}
                if tool_result_blocks is None:
                    converted.append({'role': 'user', 'content': [block]})
                    tool_result_blocks = converted[-1]['content']
                else:
                    tool_result_blocks.append(block)
            elif role == 'assistant':
                tool_result_blocks = None
                blocks = []
                if content:
                    blocks.append({'type': 'text', 'text': content})
                for tool_call in message.get('tool_calls') or []:
                    function = tool_call.get('function') or {}
                    tool_use_id = f'toolu_{tool_call_counter}'
                    tool_call_counter += 1
                    pending_tool_use_ids.append(tool_use_id)
                    blocks.append({
                        'type': 'tool_use',
                        'id': tool_use_id,
                        'name': function.get('name') or '',
                        'input': function.get('arguments') or {}
                    })
                converted.append({'role': 'assistant', 'content': blocks or [{'type': 'text', 'text': ''}]})
            else: # user
                tool_result_blocks = None
                blocks = []
                if content:
                    blocks.append({'type': 'text', 'text': content})
                for image_data in message.get('images') or []:
                    blocks.append({
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': _image_mime_type(image_data),
                            'data': image_data
                        }
                    })
                converted.append({'role': 'user', 'content': blocks or [{'type': 'text', 'text': ''}]})
        return '\n\n'.join(system_parts), converted


    # Convert internal OpenAI-format tool definitions to Anthropic tool definitions
    def _convert_tools(self, tools):
        converted = []
        for tool in tools or []:
            function = tool.get('function') or tool
            converted.append({
                'name': function.get('name') or '',
                'description': function.get('description') or '',
                'input_schema': function.get('input_schema') or function.get('parameters') or {}
            })
        return converted


# Sniff a base64 image's MIME type (JPEG starts FF D8, everything else is treated as PNG)
def _image_mime_type(image_data):
    try:
        first_bytes = base64.b64decode(image_data[:16] + '===')
    except (ValueError, TypeError):
        return 'image/png'
    return 'image/jpeg' if first_bytes[:2] == b'\xff\xd8' else 'image/png'


# Finalize the streamed tool calls into internal-format tool calls ({'function': {'name',
# 'arguments': dict}}), parsing each arguments JSON string
def _finalize_tool_calls(tool_call_states):
    tool_calls = []
    for _index, call_state in sorted(tool_call_states.items()):
        try:
            arguments = json.loads(call_state['arguments']) if call_state['arguments'] else {}
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        tool_calls.append({'function': {'name': call_state['name'], 'arguments': arguments}})
    return tool_calls
