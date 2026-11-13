# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The OpenAI-compatible provider adapter. One adapter serves OpenAI, Mistral, Groq, DeepSeek,
OpenRouter, OpenCode and any user-added "Custom" server - they differ only in their base URL
and API key. Converts between the internal message/chunk format (the Ollama chat API format)
and the OpenAI chat completions format.
"""

import base64
import json
import re

from .base import ProviderError
from .defaults import provider_base_url
from .http import HTTPProvider, _error_text, _response_json
from .stream import iter_sse_json


# Best-effort model-name heuristics for vision and thinking support, for providers that
# don't report model capabilities (best-effort only - the names evolve)
_RE_VISION_MODEL = re.compile(
    r'vision|-vl\b|llava|pixtral|moondream|minicpm-v|glm-4v|gpt-4o|gpt-4\.1|gpt-4-turbo|gemini|gemma[3-9]',
    re.IGNORECASE
)
_RE_THINKING_MODEL = re.compile(
    r'reasoner|-r[1-9]\b|\bo[1-9]\b|thinking|qwq|qwen3|gpt-5|magistral',
    re.IGNORECASE
)


# The OpenAI-compatible chat provider
class OpenAICompatProvider(HTTPProvider):
    __slots__ = ()


    supports_tools = True


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
            {'id': model.get('id') or '', 'name': model.get('name') or model.get('id') or ''}
            for model in (models or [])
            if isinstance(model, dict) and model.get('id')
        ]


    def model_capabilities(self, model):
        # Best-effort model-name heuristics - OpenAI-compatible APIs don't report model
        # capabilities
        return {
            'tools': self.supports_tools,
            'vision': bool(_RE_VISION_MODEL.search(model)),
            'thinking': bool(_RE_THINKING_MODEL.search(model))
        }


    def chat_stream(self, model, messages, think=None, tools=None, num_ctx=None, capabilities=None):
        # "num_ctx" is an Ollama-only option; thinking mode needs no parameter - a thinking
        # model streams its reasoning in the delta's reasoning fields
        body = {
            'model': model,
            'messages': self._convert_messages(messages),
            'stream': True
        }
        if tools:
            body['tools'] = tools

        # Start the streaming chat request
        response = self._request('POST', self._api_url('chat/completions'), body)
        try:
            if response.status != 200:
                self._raise_for_status(response, model)

            # Stream the SSE events, converting each to an internal-format chunk. Tool calls
            # stream in argument pieces, so they are accumulated and yielded once complete.
            tool_call_states = {}
            done = False
            for event in iter_sse_json(response):
                if not isinstance(event, dict):
                    continue
                if 'error' in event:
                    raise ProviderError('ProviderError', _error_text(event['error']))
                choice = (event.get('choices') or [{}])[0] if isinstance(event.get('choices'), list) else {}
                delta = choice.get('delta') or {}
                message = {}
                thinking_text = delta.get('reasoning') or delta.get('reasoning_content')
                if thinking_text:
                    message['thinking'] = thinking_text
                if delta.get('content'):
                    message['content'] = delta['content']
                _merge_tool_call_deltas(delta.get('tool_calls'), tool_call_states)
                if choice.get('finish_reason'):
                    done = True
                if message:
                    yield {'message': message}

            # The final internal-format chunk, carrying the completed tool calls when the model
            # requested any
            tool_calls = _finalize_tool_calls(tool_call_states)
            if done or tool_calls:
                yield { \
                    'message': {'tool_calls': tool_calls} if tool_calls else {}, \
                    'done': True \
                }
        finally:
            response.close()


    def test_connection(self):
        models = self.list_models()
        return f'{self.provider_name} is available ({len(models)} models)'


    # A provider API URL - the OpenAI-compatible endpoints live under a versioned base path
    def _api_url(self, path):
        if self.config.get('type') == 'openai' \
                and not (provider_base_url(self.config) or '').rstrip('/').endswith('/v1'):
            # Tolerate a base URL saved without its version path
            path = f'v1/{path}'
        return super()._api_url(path)


    # Convert internal-format messages to OpenAI format. Tool result messages must reference
    # the tool call IDs of the assistant message that requested them - tool results follow
    # their tool calls in order, so IDs are assigned from a pending queue.
    def _convert_messages(self, messages):
        converted = []
        pending_tool_call_ids = []
        tool_call_counter = 0
        for message in messages:
            role = message.get('role')
            content = message.get('content') or ''
            if role == 'tool':
                if pending_tool_call_ids:
                    tool_call_id = pending_tool_call_ids.pop(0)
                else: # a malformed history - match the next ID the counter would assign
                    tool_call_id = f'call_{tool_call_counter}'
                    tool_call_counter += 1
                converted.append({'role': 'tool', 'tool_call_id': tool_call_id, 'content': content})
            elif role == 'assistant' and message.get('tool_calls'):
                tool_calls = []
                for tool_call in message['tool_calls']:
                    function = tool_call.get('function') or {}
                    tool_call_id = f'call_{tool_call_counter}'
                    tool_call_counter += 1
                    pending_tool_call_ids.append(tool_call_id)
                    arguments = function.get('arguments')
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments or {})
                    tool_calls.append({ \
                        'id': tool_call_id, \
                        'type': 'function', \
                        'function': {'name': function.get('name') or '', 'arguments': arguments} \
                    })
                assistant_message = {'role': 'assistant', 'content': content, 'tool_calls': tool_calls}
                converted.append(assistant_message)
            elif role == 'assistant':
                converted.append({'role': 'assistant', 'content': content})
            elif role == 'system':
                converted.append({'role': 'system', 'content': content})
            else: # user
                converted.append({'role': 'user', 'content': content, **_convert_images(message.get('images'))})
        return converted


# Convert an internal message's base64 images to OpenAI image_url content parts, returning
# the extra message members (an empty dict when there are no images)
def _convert_images(images):
    if not images:
        return {}
    content_parts = [{'type': 'text', 'text': ''}]
    for image_data in images:
        content_parts.append({
            'type': 'image_url',
            'image_url': {'url': f'data:{_image_mime_type(image_data)};base64,{image_data}'}
        })
    return {'content': content_parts}


# Sniff a base64 image's MIME type (JPEG starts FF D8, everything else is treated as PNG)
def _image_mime_type(image_data):
    try:
        first_bytes = base64.b64decode(image_data[:16] + '===')
    except (ValueError, TypeError):
        return 'image/png'
    return 'image/jpeg' if first_bytes[:2] == b'\xff\xd8' else 'image/png'


# Merge a stream of OpenAI tool-call deltas into "tool_call_states" - a dict of stream index to
# the accumulated call state ({'id', 'name', 'arguments'}), where "arguments" is the JSON
# arguments string built up piece by piece
def _merge_tool_call_deltas(deltas, tool_call_states):
    for delta in deltas if isinstance(deltas, list) else []:
        index = delta.get('index') or 0
        call_state = tool_call_states.setdefault(index, {'id': '', 'name': '', 'arguments': ''})
        if delta.get('id'):
            call_state['id'] = delta['id']
        function_delta = delta.get('function') or {}
        if function_delta.get('name'):
            call_state['name'] += function_delta['name']
        if function_delta.get('arguments'):
            call_state['arguments'] += function_delta['arguments']


# Finalize the streamed tool calls into internal-format tool calls ({'function': {'name',
# 'arguments': dict}}), parsing each arguments JSON string
def _finalize_tool_calls(merged_states):
    tool_calls = []
    for _index, call_state in sorted(merged_states.items()):
        try:
            arguments = json.loads(call_state['arguments']) if call_state['arguments'] else {}
        except json.JSONDecodeError:
            arguments = {}
        if not isinstance(arguments, dict):
            arguments = {}
        tool_calls.append({'function': {'name': call_state['name'], 'arguments': arguments}})
    return tool_calls
