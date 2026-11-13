# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import base64
import json
import unittest
import unittest.mock

import urllib3

from ollama_chat.providers.anthropic import AnthropicProvider
from ollama_chat.providers.base import ProviderError
from ollama_chat.providers.crypto import CryptoManager
from ollama_chat.providers.openai_compat import _image_mime_type

from .util import create_test_files


def make_provider(config=None, crypto=None):
    pool_manager = unittest.mock.Mock()
    provider = AnthropicProvider(
        pool_manager,
        {'id': 'anthropic', 'name': 'Anthropic', 'type': 'anthropic', **(config or {})},
        crypto=crypto
    )
    return provider, pool_manager


def make_sse_response(events):
    body = ''.join(f'event: {e.get("type")}\ndata: {json.dumps(e)}\n\n' for e in events)
    body += 'event: message_stop\ndata: {"type": "message_stop"}\n\n'
    response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
    response.status = 200
    response.read_chunked.return_value = iter([body.encode('utf-8')])
    return response


def make_json_response(status, body):
    response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
    response.status = status
    response.json.return_value = body
    response.data = json.dumps(body).encode('utf-8')
    return response


class TestMessageConversion(unittest.TestCase):

    def test_plain_messages(self):
        provider, _pool_manager = make_provider()
        system, converted = provider._convert_messages([
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi'},
            {'role': 'user', 'content': 'Bye'}
        ])
        self.assertEqual(system, 'You are helpful')
        self.assertEqual(converted, [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Hello'}]},
            {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Hi'}]},
            {'role': 'user', 'content': [{'type': 'text', 'text': 'Bye'}]}
        ])


    def test_images(self):
        jpeg = base64.b64encode(b'\xff\xd8\xff\xe0jpeg').decode('utf-8')
        provider, _pool_manager = make_provider()
        system, converted = provider._convert_messages([
            {'role': 'user', 'content': 'What?', 'images': [jpeg]}
        ])
        self.assertEqual(converted[0]['content'][1], {
            'type': 'image',
            'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': jpeg}
        })


    def test_tool_calls_and_results(self):
        provider, _pool_manager = make_provider()
        system, converted = provider._convert_messages([
            {'role': 'user', 'content': 'Search'},
            {
                'role': 'assistant', 'content': '',
                'tool_calls': [{'function': {'name': 'web_search', 'arguments': {'query': 'x'}}}]
            },
            {'role': 'tool', 'tool_name': 'web_search', 'content': 'result'},
            {'role': 'assistant', 'content': 'Answer'}
        ])
        self.assertEqual(converted[1]['content'][0]['type'], 'tool_use')
        self.assertEqual(converted[1]['content'][0]['name'], 'web_search')
        self.assertEqual(converted[1]['content'][0]['input'], {'query': 'x'})
        # tool result merged into a user message
        self.assertEqual(converted[2]['role'], 'user')
        self.assertEqual(converted[2]['content'][0]['type'], 'tool_result')
        self.assertEqual(converted[2]['content'][0]['content'], 'result')


    def test_tools_converted(self):
        provider, _pool_manager = make_provider()
        tools = [{'type': 'function', 'function': {'name': 'web_search', 'description': 'd', 'parameters': {'type': 'object'}}}]
        self.assertEqual(provider._convert_tools(tools), [{
            'name': 'web_search', 'description': 'd', 'input_schema': {'type': 'object'}
        }])


class TestChatStream(unittest.TestCase):

    def test_content_stream(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'type': 'message_start', 'message': {'usage': {'input_tokens': 5, 'output_tokens': 0}}},
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'text'}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': 'Hello'}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': ' world'}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 3}}
        ])
        chunks = list(provider.chat_stream('claude-sonnet-4-5', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(chunks, [
            {'message': {'content': 'Hello'}},
            {'message': {'content': ' world'}},
            {'message': {}, 'done': True}
        ])
        request = pool_manager.request.call_args
        self.assertEqual(request.args[1], 'https://api.anthropic.com/v1/messages')
        body = request.kwargs['json']
        self.assertEqual(body['model'], 'claude-sonnet-4-5')
        self.assertEqual(body['max_tokens'], 4096)
        self.assertTrue(body['stream'])
        self.assertEqual(body['messages'], [{'role': 'user', 'content': [{'type': 'text', 'text': 'Hi'}]}])
        self.assertNotIn('tools', body)
        self.assertEqual(request.kwargs['headers']['anthropic-version'], '2023-06-01')


    def test_thinking(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'thinking'}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'thinking_delta', 'thinking': 'hmm'}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'content_block_start', 'index': 1, 'content_block': {'type': 'text'}},
            {'type': 'content_block_delta', 'index': 1, 'delta': {'type': 'text_delta', 'text': 'Answer'}},
            {'type': 'content_block_stop', 'index': 1},
            {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}}
        ])
        chunks = list(provider.chat_stream('claude-sonnet-4-5', [{'role': 'user', 'content': 'Hi'}], think=True))
        self.assertEqual(chunks[0]['message'], {'thinking': 'hmm'})
        self.assertEqual(chunks[1]['message'], {'content': 'Answer'})
        body = pool_manager.request.call_args.kwargs['json']
        self.assertEqual(body['thinking'], {'type': 'enabled', 'budget_tokens': 2048})


    def test_tool_call_deltas(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'type': 'content_block_start', 'index': 0, 'content_block': {'type': 'tool_use', 'id': 'toolu_0', 'name': 'web_search'}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'input_json_delta', 'partial_json': '{"qu'}},
            {'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'input_json_delta', 'partial_json': 'ery": "x"}'}},
            {'type': 'content_block_stop', 'index': 0},
            {'type': 'message_delta', 'delta': {'stop_reason': 'tool_use'}}
        ])
        chunks = list(provider.chat_stream('claude-sonnet-4-5', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['done'], True)
        self.assertEqual(chunks[0]['message']['tool_calls'], [{
            'function': {'name': 'web_search', 'arguments': {'query': 'x'}}
        }])


    def test_stream_error_event(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'Overloaded'}}
        ])
        with self.assertRaises(ProviderError) as caught:
            list(provider.chat_stream('claude-sonnet-4-5', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(caught.exception.code, 'ProviderError')
        self.assertIn('Overloaded', caught.exception.message)


class TestErrors(unittest.TestCase):

    def test_invalid_api_key(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(401, {'error': {'type': 'authentication_error', 'message': 'bad key'}})
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'InvalidApiKey')

    def test_rate_limited_retries(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = [
            make_json_response(429, {'error': {'message': 'slow'}}),
            make_json_response(429, {'error': {'message': 'slow'}}),
            make_json_response(200, {'data': [{'id': 'm1', 'display_name': 'M1'}]})
        ]
        with unittest.mock.patch('ollama_chat.providers.http.time.sleep'):
            models = provider.list_models()
        self.assertEqual(models, [{'id': 'm1', 'name': 'M1'}])
        self.assertEqual(pool_manager.request.call_count, 3)

    def test_rate_limited_exhausted(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(429, {'error': {'message': 'slow'}})
        with unittest.mock.patch('ollama_chat.providers.http.time.sleep'):
            with self.assertRaises(ProviderError) as caught:
                provider.list_models()
        self.assertEqual(caught.exception.code, 'RateLimited')
        self.assertEqual(pool_manager.request.call_count, 3)

    def test_server_error_retries_then_unavailable(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = [
            make_json_response(503, {'error': {'message': 'down'}}),
            make_json_response(503, {'error': {'message': 'down'}}),
            make_json_response(503, {'error': {'message': 'down'}})
        ]
        with unittest.mock.patch('ollama_chat.providers.http.time.sleep'):
            with self.assertRaises(ProviderError) as caught:
                provider.test_connection()
        self.assertEqual(caught.exception.code, 'ProviderUnavailable')
        self.assertEqual(pool_manager.request.call_count, 3)

    def test_model_not_found(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(
            404, {'error': {'message': 'The model `claude-nope` does not exist'}}
        )
        with self.assertRaises(ProviderError) as caught:
            list(provider.chat_stream('claude-nope', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(caught.exception.code, 'UnknownModel')

    def test_connection_failed(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = urllib3.exceptions.NewConnectionError('pool', 'refused')
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'ConnectionFailed')
        self.assertIn('Could not connect to Anthropic', caught.exception.message)

    def test_bad_api_key_ciphertext(self):
        with create_test_files([]) as temp_dir:
            from .test_providers import make_app
            app = make_app(temp_dir)
            provider, _pool_manager = make_provider({'apiKeyEnc': 'aa:bb:cc'}, crypto=app.crypto)
            with self.assertRaises(ProviderError) as caught:
                provider.test_connection()
            self.assertEqual(caught.exception.code, 'BadApiKey')


class TestApiKey(unittest.TestCase):

    def test_authorization_header(self):
        with create_test_files([]) as temp_dir:
            from .test_providers import make_app
            app = make_app(temp_dir)
            encrypted = app.crypto.encrypt_api_key('sk-ant-secret')
            provider, pool_manager = make_provider({'apiKeyEnc': encrypted}, crypto=app.crypto)
            pool_manager.request.return_value = make_json_response(200, {'data': [{'id': 'm1', 'display_name': 'M1'}]})
            provider.list_models()
            headers = pool_manager.request.call_args.kwargs['headers']
            self.assertEqual(headers['x-api-key'], 'sk-ant-secret')
            self.assertEqual(headers['anthropic-version'], '2023-06-01')

    def test_keyless(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {'data': [{'id': 'm1', 'display_name': 'M1'}]})
        provider.list_models()
        headers = pool_manager.request.call_args.kwargs['headers']
        self.assertNotIn('x-api-key', headers)


class TestModelsAndCapabilities(unittest.TestCase):

    def test_list_models(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {
            'data': [{'id': 'claude-sonnet-4-5', 'display_name': 'Claude Sonnet'}]
        })
        self.assertEqual(provider.list_models(), [{'id': 'claude-sonnet-4-5', 'name': 'Claude Sonnet'}])

    def test_capabilities(self):
        provider, _pool_manager = make_provider()
        self.assertEqual(provider.model_capabilities('claude-sonnet-4-5'), {
            'tools': True, 'vision': True, 'thinking': True
        })

    def test_test_connection(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {'data': [{'id': 'a'}, {'id': 'b'}]})
        self.assertEqual(provider.test_connection(), 'Anthropic is available (2 models)')

    def test_missing_base_url(self):
        provider, _pool_manager = make_provider({'id': 'custom', 'type': 'custom', 'baseUrl': ''})
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'BadBaseUrl')

    def test_max_tokens(self):
        provider, pool_manager = make_provider({'maxTokens': 2048})
        pool_manager.request.return_value = make_sse_response([])
        try:
            list(provider.chat_stream('claude-sonnet-4-5', [{'role': 'user', 'content': 'Hi'}]))
        except Exception:
            pass
        body = pool_manager.request.call_args.kwargs['json']
        self.assertEqual(body['max_tokens'], 2048)
