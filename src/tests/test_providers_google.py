# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import base64
import json
import unittest
import unittest.mock

import urllib3

from ollama_chat.providers.base import ProviderError
from ollama_chat.providers.google import GoogleProvider
from ollama_chat.providers.crypto import CryptoManager

from .util import create_test_files


def make_provider(config=None, crypto=None):
    pool_manager = unittest.mock.Mock()
    provider = GoogleProvider(
        pool_manager,
        {'id': 'google', 'name': 'Google (Gemini)', 'type': 'google', **(config or {})},
        crypto=crypto
    )
    return provider, pool_manager


def make_sse_response(events):
    body = ''.join(f'data: {json.dumps(event)}\n\n' for event in events)
    body += 'data: [DONE]\n\n'
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
            {'role': 'user', 'parts': [{'text': 'Hello'}]},
            {'role': 'model', 'parts': [{'text': 'Hi'}]},
            {'role': 'user', 'parts': [{'text': 'Bye'}]}
        ])


    def test_images(self):
        jpeg = base64.b64encode(b'\xff\xd8\xff\xe0jpeg').decode('utf-8')
        provider, _pool_manager = make_provider()
        system, converted = provider._convert_messages([
            {'role': 'user', 'content': 'What?', 'images': [jpeg]}
        ])
        self.assertEqual(converted[0]['parts'][1], {
            'inlineData': {'mimeType': 'image/jpeg', 'data': jpeg}
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
        self.assertEqual(converted[1]['parts'][0], {'functionCall': {'name': 'web_search', 'args': {'query': 'x'}}})
        self.assertEqual(converted[2]['parts'][0]['functionResponse']['name'], 'web_search')
        self.assertEqual(converted[2]['parts'][0]['functionResponse']['response'], {'content': 'result'})


    def test_tools_converted(self):
        provider, _pool_manager = make_provider()
        tools = [{'type': 'function', 'function': {'name': 'web_search', 'description': 'd', 'parameters': {'type': 'object'}}}]
        self.assertEqual(provider._convert_tools(tools), [{
            'name': 'web_search', 'description': 'd', 'parameters': {'type': 'object'}
        }])


class TestChatStream(unittest.TestCase):

    def test_content_stream(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'Hello'}]}}]},
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': ' world'}]}, 'finishReason': 'STOP'}]}
        ])
        chunks = list(provider.chat_stream('gemini-2.5-flash', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(chunks, [
            {'message': {'content': 'Hello'}},
            {'message': {'content': ' world'}},
            {'message': {}, 'done': True}
        ])
        request = pool_manager.request.call_args
        self.assertIn('models/gemini-2.5-flash:streamGenerateContent', request.args[1])
        self.assertIn('alt=sse', request.args[1])
        body = request.kwargs['json']
        self.assertEqual(body['contents'], [{'role': 'user', 'parts': [{'text': 'Hi'}]}])
        self.assertNotIn('tools', body)


    def test_thinking(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'hmm', 'thought': True}]}}]},
            {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'Answer'}]}, 'finishReason': 'STOP'}]}
        ])
        chunks = list(provider.chat_stream('gemini-2.5-flash', [{'role': 'user', 'content': 'Hi'}], think=True))
        self.assertEqual(chunks[0]['message'], {'thinking': 'hmm'})
        self.assertEqual(chunks[1]['message'], {'content': 'Answer'})
        body = pool_manager.request.call_args.kwargs['json']
        self.assertEqual(body['generationConfig'], {'thinkingConfig': {'thinkingBudget': -1}})


    def test_tool_calls(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'candidates': [{'content': {'role': 'model', 'parts': [
                {'functionCall': {'name': 'web_search', 'args': {'query': 'x'}}}
            ]}, 'finishReason': 'STOP'}]}
        ])
        chunks = list(provider.chat_stream('gemini-2.5-flash', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['done'], True)
        self.assertEqual(chunks[0]['message']['tool_calls'], [{
            'function': {'name': 'web_search', 'arguments': {'query': 'x'}}
        }])


    def test_stream_error_event(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_sse_response([
            {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT'}}
        ])
        with self.assertRaises(ProviderError) as caught:
            list(provider.chat_stream('gemini-2.5-flash', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(caught.exception.code, 'InvalidApiKey')


class TestErrors(unittest.TestCase):

    def test_invalid_api_key(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(400, {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT'}})
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'InvalidApiKey')

    def test_rate_limited_retries(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = [
            make_json_response(429, {'error': {'message': 'slow'}}),
            make_json_response(429, {'error': {'message': 'slow'}}),
            make_json_response(200, {'models': [{'name': 'models/gemini-2.0-flash', 'displayName': 'Gemini 2.0 Flash'}]})
        ]
        with unittest.mock.patch('ollama_chat.providers.http.time.sleep'):
            models = provider.list_models()
        self.assertEqual(models, [{'id': 'gemini-2.0-flash', 'name': 'Gemini 2.0 Flash'}])
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
            404, {'error': {'message': 'Model `gemini-nope` not found'}}
        )
        with self.assertRaises(ProviderError) as caught:
            list(provider.chat_stream('gemini-nope', [{'role': 'user', 'content': 'Hi'}]))
        self.assertEqual(caught.exception.code, 'UnknownModel')

    def test_connection_failed(self):
        provider, pool_manager = make_provider()
        pool_manager.request.side_effect = urllib3.exceptions.NewConnectionError('pool', 'refused')
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'ConnectionFailed')
        self.assertIn('Could not connect to Google', caught.exception.message)

    def test_bad_api_key_ciphertext(self):
        with create_test_files([]) as temp_dir:
            from .test_providers import make_app
            app = make_app(temp_dir)
            provider, _pool_manager = make_provider({'apiKeyEnc': 'aa:bb:cc'}, crypto=app.crypto)
            with self.assertRaises(ProviderError) as caught:
                provider.test_connection()
            self.assertEqual(caught.exception.code, 'BadApiKey')


class TestApiKey(unittest.TestCase):

    def test_authorization_query(self):
        with create_test_files([]) as temp_dir:
            from .test_providers import make_app
            app = make_app(temp_dir)
            encrypted = app.crypto.encrypt_api_key('AIza-secret')
            provider, pool_manager = make_provider({'apiKeyEnc': encrypted}, crypto=app.crypto)
            pool_manager.request.return_value = make_json_response(200, {'models': []})
            provider.list_models()
            url = pool_manager.request.call_args.args[1]
            self.assertIn('key=AIza-secret', url)

    def test_keyless_custom_server(self):
        # Google requires a key - missing key still sends an empty key param
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {'models': []})
        provider.list_models()
        url = pool_manager.request.call_args.args[1]
        self.assertIn('key=', url)


class TestModelsAndCapabilities(unittest.TestCase):

    def test_list_models(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {
            'models': [
                {'name': 'models/gemini-2.5-flash', 'displayName': 'Gemini 2.5 Flash'},
                {'name': 'models/gemini-1.5-pro', 'displayName': 'Gemini 1.5 Pro'}
            ]
        })
        self.assertEqual(provider.list_models(), [
            {'id': 'gemini-2.5-flash', 'name': 'Gemini 2.5 Flash'},
            {'id': 'gemini-1.5-pro', 'name': 'Gemini 1.5 Pro'}
        ])

    def test_capabilities(self):
        provider, _pool_manager = make_provider()
        self.assertEqual(provider.model_capabilities('gemini-2.5-flash'), {
            'tools': True, 'vision': True, 'thinking': True
        })
        self.assertEqual(provider.model_capabilities('gemini-1.5-pro'), {
            'tools': True, 'vision': True, 'thinking': False
        })

    def test_test_connection(self):
        provider, pool_manager = make_provider()
        pool_manager.request.return_value = make_json_response(200, {'models': [{'name': 'models/a'}, {'name': 'models/b'}]})
        self.assertEqual(provider.test_connection(), 'Google (Gemini) is available (2 models)')

    def test_missing_base_url(self):
        provider, _pool_manager = make_provider({'id': 'custom', 'type': 'custom', 'baseUrl': ''})
        with self.assertRaises(ProviderError) as caught:
            provider.test_connection()
        self.assertEqual(caught.exception.code, 'BadBaseUrl')
