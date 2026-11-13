# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import base64
import json
import unittest
import unittest.mock

import urllib3

from ollama_chat.providers.base import ProviderError
from ollama_chat.providers.crypto import CryptoManager
from ollama_chat.providers.openai_compat import OpenAICompatProvider

from .util import create_test_files


# A JPEG's first bytes, as base64
_JPEG_BASE64 = base64.b64encode(b'\xff\xd8\xff\xe0jpeg-data').decode('utf-8')
_PNG_BASE64 = base64.b64encode(b'\x89PNG\r\n\x1a\npng-data').decode('utf-8')


# Helper to create a provider with a mock pool manager
def make_provider(config=None, crypto=None):
    pool_manager = unittest.mock.Mock()
    provider = OpenAICompatProvider(
        pool_manager,
        {'id': 'openai', 'name': 'OpenAI', 'type': 'openai', **(config or {})},
        crypto=crypto
    )
    return provider, pool_manager


# Helper to create a mock streaming response whose "read_chunked" yields "data" SSE bytes
def make_sse_response(events):
    body = ''.join(f'data: {json.dumps(event)}\n\n' for event in events) + 'data: [DONE]\n\n'
    response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
    response.status = 200
    response.read_chunked.return_value = iter([body.encode('utf-8')])
    return response


# Helper to create a mock non-streaming JSON response
def make_json_response(status, body):
    response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
    response.status = status
    response.json.return_value = body
    response.data = json.dumps(body).encode('utf-8')
    return response


class TestMessageConversion(unittest.TestCase):

    def test_plain_messages(self):
        provider, _pool_manager = make_provider()
        converted = provider._convert_messages([
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi'},
            {'role': 'user', 'content': 'Bye'}
        ])
        self.assertEqual(converted, [
            {'role': 'system', 'content': 'You are helpful'},
            {'role': 'user', 'content': 'Hello'},
            {'role': 'assistant', 'content': 'Hi'},
            {'role': 'user', 'content': 'Bye'}
        ])


    def test_image_sniffing(self):
        provider, _pool_manager = make_provider()
        converted = provider._convert_messages([
            {'role': 'user', 'content': 'What?', 'images': [_JPEG_BASE64, _PNG_BASE64]}
        ])
        self.assertEqual(len(converted), 1)
        content = converted[0]['content']
        self.assertEqual(content[0], {'type': 'text', 'text': ''})
        self.assertEqual(
            content[1],
            {'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{_JPEG_BASE64}'}}
        )
        self.assertEqual(
            content[2],
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{_PNG_BASE64}'}}
        )


    def test_tool_calls_and_results(self):
        provider, _pool_manager = make_provider()
        converted = provider._convert_messages([
            {'role': 'user', 'content': 'Search'},
            {
                'role': 'assistant', 'content': '',
                'tool_calls': [{'function': {'name': 'web_search', 'arguments': {'query': 'x'}}}]
            },
            {'role': 'tool', 'tool_name': 'web_search', 'content': 'result'},
            {'role': 'assistant', 'content': 'Answer'}
        ])
        self.assertEqual(converted[1]['tool_calls'], [{
            'id': 'call_0',
            'type': 'function',
            'function': {'name': 'web_search', 'arguments': '{"query": "x"}'}
        }])
        # The tool result references the assistant message's tool call ID
        self.assertEqual(converted[2], {'role': 'tool', 'tool_call_id': 'call_0', 'content': 'result'})
        self.assertEqual(converted[3], {'role': 'assistant', 'content': 'Answer'})


    def test_tool_rounds_two(self):
        provider, _pool_manager = make_provider()
        converted = provider._convert_messages([
            {'role': 'user', 'content': 'Go'},
            {
                'role': 'assistant', 'content': '',
                'tool_calls': [{'function': {'name': 't1', 'arguments': {}}}]
            },
            {'role': 'tool', 'tool_name': 't1', 'content': 'r1'},
            {
                'role': 'assistant', 'content': '',
                'tool_calls': [{'function': {'name': 't2', 'arguments': {}}}]
            },
            {'role': 'tool', 'tool_name': 't2', 'content': 'r2'}
        ])
        self.assertEqual(converted[1]['tool_calls'][0]['id'], 'call_0')
        self.assertEqual(converted[2]['tool_call_id'], 'call_0')
        self.assertEqual(converted[3]['tool_calls'][0]['id'], 'call_1')
        self.assertEqual(converted[4]['tool_call_id'], 'call_1')


class TestChatStream(unittest.TestCase):

    def test_content_stream(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'choices': [{'delta': {'content': 'Hello'}}]},
            {'choices': [{'delta': {'reasoning': 'hmm'}}]},
            {'choices': [{'delta': {'content': ' world'}, 'finish_reason': 'stop'}]}
        ])
        chunks = list(provider.chat_stream('gpt-4o', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(chunks, [
            {'message': {'content': 'Hello'}},
            {'message': {'thinking': 'hmm'}},
            {'message': {'content': ' world'}},
            {'message': {}, 'done': True}
        ])
        # The chat completions request body
        request = pool_manager.request.call_args
        self.assertEqual(request.args[0], 'POST')
        self.assertEqual(request.args[1], 'https://api.openai.com/v1/chat/completions')
        body = request.kwargs['json']
        self.assertEqual(body['model'], 'gpt-4o')
        self.assertTrue(body['stream'])
        self.assertEqual(body['messages'], [{'role': 'user', 'content': 'Hi'}])
        self.assertNotIn('tools', body)


    def test_tool_call_deltas(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {
                'choices': [{
                    'delta': {'tool_calls': [
                        {'index': 0, 'id': 'call_9', 'function': {'name': 'web_', 'arguments': '{"qu'}}
                    ]}
                }]
            },
            {
                'choices': [{
                    'delta': {'tool_calls': [
                        {'index': 0, 'function': {'name': 'search', 'arguments': 'ery": "x"}'}}
                    ]}
                }]
            },
            {'choices': [{'delta': {}, 'finish_reason': 'tool_calls'}]}
        ])
        chunks = list(provider.chat_stream('gpt-4o', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['done'], True)
        self.assertEqual(chunks[0]['message']['tool_calls'], [{
            'function': {'name': 'web_search', 'arguments': {'query': 'x'}}
        }])


    def test_reasoning_content_field(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'choices': [{'delta': {'reasoning_content': 'thinking...', 'content': 'Answer'}}]}
        ])
        chunks = list(provider.chat_stream('deepseek-r1', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(chunks[0]['message'], {'thinking': 'thinking...', 'content': 'Answer'})


    def test_stream_error_event(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'error': {'message': 'The server is overloaded'}}
        ])
        with self.assertRaises(ProviderError) as caught:
            list(provider.chat_stream('gpt-4o', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(caught.exception.code, 'ProviderError')
        self.assertIn('overloaded', caught.exception.message)


class TestErrors(unittest.TestCase):

    def test_invalid_api_key(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(401, {'error': {'message': 'bad key'}})
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'InvalidApiKey')
        self.assertIn('rejected the API key', caught.exception.message)
        self.assertIn('Check the API key in settings', caught.exception.message)


    def test_rate_limited_retries(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = [
            make_json_response(429, {'error': {'message': 'slow down'}}),
            make_json_response(429, {'error': {'message': 'slow down'}}),
            make_json_response(200, {'data': [{'id': 'm1'}]})
        ]
        with unittest.mock.patch('ollama_chat.providers.http.time.sleep') as mock_sleep:
            models = provider.list_models()
        self.assertEqual(models, [{'id': 'm1', 'name': 'm1'}])
        self.assertEqual(pool_manager.request.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)


    def test_rate_limited_exhausted(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(429, {'error': {'message': 'slow down'}})
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
            404, {'error': {'message': 'The model `gpt-nope` does not exist'}}
        )
        with self.assertRaises(ProviderError) as caught:
            list(provider.chat_stream('gpt-nope', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(caught.exception.code, 'UnknownModel')
        self.assertIn('gpt-nope', caught.exception.message)


    def test_connection_failed(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = urllib3.exceptions.NewConnectionError('pool', 'refused')
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'ConnectionFailed')
        self.assertIn('Could not connect to OpenAI', caught.exception.message)


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
            encrypted = app.crypto.encrypt_api_key('sk-secret-123456')
            provider, pool_manager = make_provider({'apiKeyEnc': encrypted}, crypto=app.crypto)
            pool_manager.request.return_value = make_json_response(200, {'data': [{'id': 'm1'}]})
            provider.list_models()
            headers = pool_manager.request.call_args.kwargs['headers']
            self.assertEqual(headers['Authorization'], 'Bearer sk-secret-123456')


    def test_keyless_custom_server(self):
        provider, pool_manager = make_provider({'type': 'custom', 'baseUrl': 'http://localhost:1234/v1'})
        pool_manager.request.return_value = make_json_response(200, {'data': [{'id': 'llm'}]})
        models = provider.list_models()
        self.assertEqual(models, [{'id': 'llm', 'name': 'llm'}])
        headers = pool_manager.request.call_args.kwargs['headers']
        self.assertNotIn('Authorization', headers)


    def test_saved_key_without_crypto(self):
        provider, _pool_manager = make_provider({'apiKeyEnc': 'aa:bb:cc'}, crypto=None)
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'BadApiKey')


class TestModelsAndCapabilities(unittest.TestCase):

    def test_list_models(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {
            'data': [{'id': 'gpt-4o', 'name': 'GPT-4o'}, {'id': 'o1'}, {'id': ''}, 'junk']
        })
        models = provider.list_models()
        self.assertEqual(models, [{'id': 'gpt-4o', 'name': 'GPT-4o'}, {'id': 'o1', 'name': 'o1'}])


    def test_list_models_plain_list(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, [{'id': 'llm', 'name': 'Local'}])
        self.assertEqual(provider.list_models(), [{'id': 'llm', 'name': 'Local'}])


    def test_capabilities(self):
        provider, _pool_manager = make_provider()
        self.assertEqual(provider.model_capabilities('llama3'), {
            'tools': True, 'vision': False, 'thinking': False
        })
        self.assertEqual(provider.model_capabilities('gpt-4o'), {
            'tools': True, 'vision': True, 'thinking': False
        })
        self.assertEqual(provider.model_capabilities('deepseek-r1'), {
            'tools': True, 'vision': False, 'thinking': True
        })


    def test_test_connection(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {'data': [{'id': 'a'}, {'id': 'b'}]})
        self.assertEqual(provider.test_connection(), 'OpenAI is available (2 models)')


    def test_missing_base_url(self):
        provider, _pool_manager = make_provider({'id': 'custom', 'type': 'custom', 'baseUrl': ''})
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'BadBaseUrl')
        self.assertIn('no base URL', caught.exception.message)


    def test_crypto_optional(self):
        crypto = CryptoManager('unused.json')
        provider, _pool_manager = make_provider(crypto=crypto)
        self.assertIs(provider.crypto, crypto)


class TestChatIntegration(unittest.TestCase):

    # A config whose conversation uses the OpenAI provider
    CONFIG = {
        'conversations': [
            {'id': 'conv1', 'model': 'gpt-4o', 'provider': 'openai', 'title': 'Conversation 1', 'exchanges': []}
        ]
    }


    def test_openai_round_trip(self):
        with create_test_files([('ollama-chat.json', json.dumps(self.CONFIG))]) as temp_dir, \
             unittest.mock.patch('threading.Thread'):
            from .test_providers import make_app
            app = make_app(temp_dir)
            app.pool_manager = unittest.mock.Mock()
            app.pool_manager.request.return_value = make_sse_response([
                {'choices': [{'delta': {'content': 'Hi'}}]},
                {'choices': [{'delta': {'content': ' there'}, 'finish_reason': 'stop'}]}
            ])

            from ollama_chat.chat import ChatManager
            ChatManager.chat_thread_fn(ChatManager(app, 'conv1', ['Hello']))
            with app.config() as config:
                exchange = config['conversations'][0]['exchanges'][0]
            self.assertEqual(exchange['user'], 'Hello')
            self.assertEqual(exchange['model'], 'Hi there')


    def test_openai_thinking(self):
        with create_test_files([('ollama-chat.json', json.dumps(self.CONFIG))]) as temp_dir, \
             unittest.mock.patch('threading.Thread'):
            from .test_providers import make_app
            app = make_app(temp_dir)
            app.pool_manager = unittest.mock.Mock()
            app.pool_manager.request.return_value = make_sse_response([
                {'choices': [{'delta': {'reasoning': 'hmm'}}]},
                {'choices': [{'delta': {'content': 'Answer'}}]}
            ])

            from ollama_chat.chat import ChatManager
            ChatManager.chat_thread_fn(ChatManager(app, 'conv1', ['Hello']))
            with app.config() as config:
                exchange = config['conversations'][0]['exchanges'][0]
            self.assertEqual(exchange['thinking'], 'hmm')
            self.assertEqual(exchange['model'], 'Answer')
