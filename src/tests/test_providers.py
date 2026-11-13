# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import json
import os
import unittest
import unittest.mock

from ollama_chat.app import OllamaChat
from ollama_chat.chat import ChatManager
from ollama_chat.providers.crypto import CryptoManager, mask_api_key

from .util import create_test_files


# A default config file's content
EMPTY_CONFIG = {'conversations': []}


# Helper to create an app for a temp directory's config file
def make_app(temp_dir):
    return OllamaChat(os.path.join(temp_dir, 'ollama-chat.json'))


# Helper to POST an API request body, returning the (status, JSON response) pair
def api_post(app, action, body):
    status, _headers, content_bytes = app.request( \
        'POST', f'/{action}', wsgi_input=json.dumps(body).encode('utf-8') \
    )
    return status, json.loads(content_bytes.decode('utf-8'))


# Helper to GET an API request, returning the (status, JSON response) pair
def api_get(app, action, query=None):
    from schema_markdown import encode_query_string
    status, _headers, content_bytes = app.request( \
        'GET', f'/{action}', query_string=encode_query_string(query or {}) \
    )
    return status, json.loads(content_bytes.decode('utf-8'))


class TestCrypto(unittest.TestCase):

    def setUp(self):
        self._temp = create_test_files([])
        self.temp_dir = self._temp.__enter__()
        self.addCleanup(self._temp.__exit__, None, None, None)
        self.config_path = os.path.join(self.temp_dir, 'ollama-chat.json')
        self.crypto = CryptoManager(self.config_path)


    def test_roundtrip(self):
        encrypted = self.crypto.encrypt_api_key('sk-secret-123456')
        self.assertNotEqual(encrypted, 'sk-secret-123456')
        self.assertNotIn('sk-secret-123456', encrypted)
        self.assertEqual(encrypted.count(':'), 2)
        self.assertEqual(self.crypto.decrypt_api_key(encrypted), 'sk-secret-123456')


    def test_empty(self):
        self.assertEqual(self.crypto.encrypt_api_key(''), '')
        self.assertEqual(self.crypto.decrypt_api_key(''), '')


    def test_master_key_file(self):
        # The master key is created next to the config file on first use and reused after
        self.assertFalse(os.path.isfile(os.path.join(self.temp_dir, 'ollama-chat.key')))
        encrypted = self.crypto.encrypt_api_key('sk-secret-123456')
        self.assertTrue(os.path.isfile(os.path.join(self.temp_dir, 'ollama-chat.key')))
        self.assertEqual(CryptoManager(self.config_path).decrypt_api_key(encrypted), 'sk-secret-123456')


    def test_bad_ciphertext(self):
        self.assertRaises(ValueError, self.crypto.decrypt_api_key, 'not-hex')
        self.assertRaises(ValueError, self.crypto.decrypt_api_key, 'aa:bb')


    def test_key_mask(self):
        self.assertEqual(mask_api_key('sk-ant-abcdef123456'), 'sk-ant••••3456')
        self.assertEqual(mask_api_key('short'), '••••')
        self.assertEqual(mask_api_key(''), '••••')


    def test_key_mask_undecryptable(self):
        # A saved key that can't be decrypted (e.g. a deleted master key) masks as hidden
        self.crypto.encrypt_api_key('sk-secret-123456')
        with open(self.crypto.key_path, 'w', encoding='utf-8') as key_fh:
            key_fh.write('00' * 32)
        self.assertEqual(self.crypto.key_mask('00:11:22'), '••••')


class TestProviderApi(unittest.TestCase):

    def test_get_providers_seeds(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            status, response = api_get(app, 'getProviders')
            self.assertEqual(status, '200 OK')
            providers = response['providers']
            self.assertEqual(
                [provider['id'] for provider in providers],
                ['ollama', 'openai', 'anthropic', 'google', 'mistral', 'groq', 'deepseek', 'openrouter', 'opencode']
            )
            ollama = providers[0]
            self.assertEqual(ollama['name'], 'Ollama')
            self.assertEqual(ollama['type'], 'ollama')
            self.assertTrue(ollama['enabled'])
            self.assertTrue(ollama['builtIn'])
            self.assertFalse(ollama['hasApiKey'])
            self.assertNotIn('apiKeyMask', ollama)
            self.assertEqual(providers[1]['baseUrl'], 'https://api.openai.com/v1')
            # The seeded providers are saved to the config file
            with app.config() as config:
                self.assertEqual(len(config['providers']), 9)


    def test_get_providers_adds_missing_builtins(self):
        test_files = [('ollama-chat.json', json.dumps({
            'conversations': [],
            'providers': [
                {'id': 'my-studio', 'name': 'My Studio', 'type': 'custom', 'builtIn': False}
            ]
        }))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            status, response = api_get(app, 'getProviders')
            self.assertEqual(status, '200 OK')
            provider_ids = [provider['id'] for provider in response['providers']]
            self.assertEqual(provider_ids[0], 'my-studio')
            self.assertIn('ollama', provider_ids)
            self.assertEqual(len(provider_ids), 10)


    def test_save_provider_custom(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            status, response = api_post(app, 'saveProvider', {
                'name': 'My LM Studio', 'baseUrl': 'http://192.168.1.5:1234/v1'
            })
            self.assertEqual(status, '200 OK')
            provider = response['provider']
            self.assertEqual(provider['id'], 'my-lm-studio')
            self.assertEqual(provider['name'], 'My LM Studio')
            self.assertEqual(provider['type'], 'custom')
            self.assertFalse(provider['builtIn'])
            self.assertTrue(provider['enabled'])
            self.assertEqual(provider['baseUrl'], 'http://192.168.1.5:1234/v1')
            self.assertNotIn('warning', response)
            self.assertEqual(response.get('warning'), None)


    def test_save_provider_custom_id_collision(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            _status, response1 = api_post(app, 'saveProvider', {'name': 'My Studio'})
            _status, response2 = api_post(app, 'saveProvider', {'name': 'My Studio'})
            self.assertEqual(response1['provider']['id'], 'my-studio')
            self.assertEqual(response2['provider']['id'], 'my-studio-1')


    def test_save_provider_api_key(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            status, response = api_post(app, 'saveProvider', {
                'id': 'openai', 'name': 'OpenAI', 'apiKey': 'sk-secret-123456'
            })
            self.assertEqual(status, '200 OK')
            self.assertTrue(response['provider']['hasApiKey'])
            self.assertEqual(response['provider']['apiKeyMask'], 'sk-sec••••3456')
            # The key is stored encrypted, never as plaintext or in the response
            self.assertNotIn('sk-secret-123456', json.dumps(response))
            with app.config() as config:
                encrypted = next(
                    provider for provider in config['providers'] if provider['id'] == 'openai'
                )['apiKeyEnc']
                self.assertNotEqual(encrypted, 'sk-secret-123456')
                self.assertEqual(app.crypto.decrypt_api_key(encrypted), 'sk-secret-123456')


    def test_save_provider_empty_key_keeps(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'apiKey': 'sk-secret-123456'})
            with app.config() as config:
                encrypted_before = next(
                    provider for provider in config['providers'] if provider['id'] == 'openai'
                )['apiKeyEnc']
            # An empty "apiKey" keeps the saved key
            _status, response = api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI'})
            self.assertTrue(response['provider']['hasApiKey'])
            with app.config() as config:
                encrypted_after = next(
                    provider for provider in config['providers'] if provider['id'] == 'openai'
                )['apiKeyEnc']
                self.assertEqual(encrypted_after, encrypted_before)


    def test_save_provider_delete_key(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'apiKey': 'sk-secret-123456'})
            _status, response = api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'deleteApiKey': True})
            self.assertFalse(response['provider']['hasApiKey'])
            self.assertNotIn('apiKeyMask', response['provider'])


    def test_save_provider_base_url(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)

            # An invalid base URL is rejected
            status, response = api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'baseUrl': 'ftp://nope'})
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'BadProvider')

            # An insecure http:// base URL warns for a cloud provider
            status, response = api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'baseUrl': 'http://api.example.com/v1'})
            self.assertEqual(status, '200 OK')
            self.assertIn('insecure', response.get('warning', ''))

            # ... but not for localhost
            status, response = api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'baseUrl': 'http://localhost:8080/v1'})
            self.assertEqual(status, '200 OK')
            self.assertNotIn('warning', response)

            # An empty base URL restores the built-in default
            status, response = api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'baseUrl': ''})
            self.assertEqual(status, '200 OK')
            self.assertEqual(response['provider']['baseUrl'], 'https://api.openai.com/v1')

            # An unknown provider is rejected
            status, response = api_post(app, 'saveProvider', {'id': 'nope', 'name': 'Nope'})
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownProvider')


    def test_delete_provider(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)

            # A built-in provider can't be deleted
            status, response = api_post(app, 'deleteProvider', {'id': 'openai'})
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'BuiltInProvider')

            # A custom provider can
            _status, response = api_post(app, 'saveProvider', {'name': 'My Studio'})
            provider_id = response['provider']['id']
            status, _response = api_post(app, 'deleteProvider', {'id': provider_id})
            self.assertEqual(status, '200 OK')
            with app.config() as config:
                self.assertNotIn(provider_id, [provider['id'] for provider in config.get('providers', [])])

            # An unknown provider is rejected
            status, response = api_post(app, 'deleteProvider', {'id': 'nope'})
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownProvider')


    def test_test_provider(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            with unittest.mock.patch( \
                'ollama_chat.providers.ollama.ollama_list', \
                return_value=[{'model': 'llm'}] \
            ):
                status, response = api_post(app, 'testProvider', {'id': 'ollama'})
            self.assertEqual(status, '200 OK')
            self.assertEqual(response['message'], 'Ollama is available (1 models)')

            # An unknown provider is rejected
            status, response = api_post(app, 'testProvider', {'id': 'nope'})
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownProvider')


    def test_get_provider_models_cache(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir:
            app = make_app(temp_dir)
            with unittest.mock.patch( \
                'ollama_chat.providers.ollama.ollama_list', \
                side_effect=[[{'model': 'a'}], [{'model': 'b'}]] \
            ) as mock_list:
                status, response = api_get(app, 'getProviderModels', {'provider': 'ollama'})
                self.assertEqual(status, '200 OK')
                self.assertEqual(response['models'], [{'id': 'a', 'name': 'a'}])
                # The cached list is served without a second fetch
                status, response = api_get(app, 'getProviderModels', {'provider': 'ollama'})
                self.assertEqual(status, '200 OK')
                self.assertEqual(response['models'], [{'id': 'a', 'name': 'a'}])
                # "refresh" bypasses the cache
                status, response = api_get(app, 'getProviderModels', {'provider': 'ollama', 'refresh': True})
                self.assertEqual(status, '200 OK')
                self.assertEqual(response['models'], [{'id': 'b', 'name': 'b'}])
                self.assertEqual(mock_list.call_count, 2)

            # An unknown provider is rejected
            status, response = api_get(app, 'getProviderModels', {'provider': 'nope'})
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownProvider')


class TestConversationProvider(unittest.TestCase):

    def test_start_conversation_provider(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            app = make_app(temp_dir)

            # A known, enabled provider is stored on the conversation
            status, response = api_post(app, 'startConversation', {
                'model': 'm', 'user': 'Hello', 'provider': 'openai'
            })
            self.assertEqual(status, '200 OK')
            with app.config() as config:
                self.assertEqual(config['conversations'][0]['provider'], 'openai')
            mock_manager.assert_called_once()

            # An unknown provider is rejected
            status, response = api_post(app, 'startConversation', {
                'model': 'm', 'user': 'Hello', 'provider': 'nope'
            })
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownProvider')


    def test_start_conversation_disabled_provider(self):
        test_files = [('ollama-chat.json', json.dumps(EMPTY_CONFIG))]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            app = make_app(temp_dir)
            api_post(app, 'saveProvider', {'id': 'openai', 'name': 'OpenAI', 'enabled': False})

            # A disabled provider is rejected
            status, response = api_post(app, 'startConversation', {
                'model': 'm', 'user': 'Hello', 'provider': 'openai'
            })
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'ProviderDisabled')
            mock_manager.assert_not_called()

            # The default provider (the config's, or Ollama) is used when none is requested
            status, response = api_post(app, 'startConversation', {'model': 'm', 'user': 'Hello'})
            self.assertEqual(status, '200 OK')
            with app.config() as config:
                self.assertEqual(config['conversations'][0]['provider'], 'ollama')


    def test_reply_conversation_provider(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [('ollama-chat.json', json.dumps(original_config))]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            app = make_app(temp_dir)

            # The reply switches the conversation's model and provider
            status, _response = api_post(app, 'replyConversation', {
                'id': 'conv1', 'user': 'Hi', 'model': 'new-m', 'provider': 'openai'
            })
            self.assertEqual(status, '200 OK')
            with app.config() as config:
                conversation = config['conversations'][0]
                self.assertEqual(conversation['model'], 'new-m')
                self.assertEqual(conversation['provider'], 'openai')
            mock_manager.assert_called_once()
            app.chats.clear()

            # An unknown provider is rejected
            status, response = api_post(app, 'replyConversation', {
                'id': 'conv1', 'user': 'Hi', 'provider': 'nope'
            })
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownProvider')


    def test_chat_disabled_provider_error(self):
        test_files = [('ollama-chat.json', json.dumps({
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'provider': 'openai', 'title': 'Conversation 1', 'exchanges': []}
            ],
            'providers': [
                {'id': 'openai', 'name': 'OpenAI', 'type': 'openai', 'enabled': False}
            ]
        }))]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            app = make_app(temp_dir)

            # The OpenAI provider is disabled in the config - the chat shows a message
            # instead of failing hard
            chat_manager = ChatManager(app, 'conv1', ['Hello'])
            ChatManager.chat_thread_fn(chat_manager)
            with app.config() as config:
                exchange = config['conversations'][0]['exchanges'][0]
            self.assertIn('The provider "OpenAI" is disabled', exchange['model'])
            self.assertIn('select another model', exchange['model'])
            self.assertIs(mock_pool_manager.return_value.request.called, False)
