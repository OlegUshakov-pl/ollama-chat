# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import json
from io import StringIO
import os
import re
import unittest
import unittest.mock

import urllib3
from schema_markdown import encode_query_string
from ollama_chat.app import DownloadManager, OllamaChat

from .util import create_test_files


class TestApp(unittest.TestCase):

    def test_init(self):
        test_files = [
            ('ollama-chat.json', json.dumps({'model': 'llm', 'conversations': []}))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            self.assertEqual(app.config.config_path, config_path)
            with app.config() as config:
                self.assertDictEqual(config, {'model': 'llm', 'conversations': []})
            self.assertDictEqual(app.chats, {})
            self.assertDictEqual(app.downloads, {})
            self.assertIsNone(app.download_error)
            self.assertListEqual(
                sorted(request.name for request in app.requests.values() if request.doc_group.startswith('Ollama Chat ')),
                [
                    'app.css',
                    'app.js',
                    'createTemplate',
                    'deleteConversation',
                    'deleteConversationExchange',
                    'deleteModel',
                    'deleteTask',
                    'deleteTemplate',
                    'downloadModel',
                    'exportPdf',
                    'getConversation',
                    'getConversations',
                    'getModels',
                    'getProfile',
                    'getSettings',
                    'getSystemInfo',
                    'getTaskLog',
                    'getTaskReport',
                    'getTasks',
                    'getTemplate',
                    'index.html',
                    'moveConversation',
                    'moveTemplate',
                    'ollamaChat.bare',
                    'ollamaChatConversation.bare',
                    'ollamaChatModels.bare',
                    'ollamaChatTemplate.bare',
                    'ollamaChatUtil.bare',
                    'regenerateConversationExchange',
                    'replyConversation',
                    'runTask',
                    'sendEmail',
                    'setConversationTitle',
                    'setEmailSettings',
                    'setModel',
                    'setProfile',
                    'setTask',
                    'setWorkspace',
                    'startConversation',
                    'startTemplate',
                    'stopConversation',
                    'stopModelDownload',
                    'testEmailConnection',
                    'updateTemplate',
                    'vendor/marked.min.js',
                    'vendor/purify.min.js'
                ]
            )


    def test_init_missing_config(self):
        with unittest.mock.patch('os.path.isfile', return_value=False) as mock_isfile:
            app = OllamaChat('ollama-chat.json')
            mock_isfile.assert_called_once_with('ollama-chat.json')
            self.assertEqual(app.config.config_path, 'ollama-chat.json')
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})
            self.assertDictEqual(app.chats, {})
            self.assertListEqual(
                sorted(request.name for request in app.requests.values() if request.doc_group.startswith('Ollama Chat ')),
                [
                    'app.css',
                    'app.js',
                    'createTemplate',
                    'deleteConversation',
                    'deleteConversationExchange',
                    'deleteModel',
                    'deleteTask',
                    'deleteTemplate',
                    'downloadModel',
                    'exportPdf',
                    'getConversation',
                    'getConversations',
                    'getModels',
                    'getProfile',
                    'getSettings',
                    'getSystemInfo',
                    'getTaskLog',
                    'getTaskReport',
                    'getTasks',
                    'getTemplate',
                    'index.html',
                    'moveConversation',
                    'moveTemplate',
                    'ollamaChat.bare',
                    'ollamaChatConversation.bare',
                    'ollamaChatModels.bare',
                    'ollamaChatTemplate.bare',
                    'ollamaChatUtil.bare',
                    'regenerateConversationExchange',
                    'replyConversation',
                    'runTask',
                    'sendEmail',
                    'setConversationTitle',
                    'setEmailSettings',
                    'setModel',
                    'setProfile',
                    'setTask',
                    'setWorkspace',
                    'startConversation',
                    'startTemplate',
                    'stopConversation',
                    'stopModelDownload',
                    'testEmailConnection',
                    'updateTemplate',
                    'vendor/marked.min.js',
                    'vendor/purify.min.js',
                ]
            )


class TestDownloadManager(unittest.TestCase):

    def setUp(self):
        # Isolate from the real workspace - a real workspace's tasks.json would start the
        # TaskManager scheduler thread (an extra threading.Thread call)
        env_patcher = unittest.mock.patch.dict(os.environ)
        os.environ['OLLAMA_CHAT_WORKSPACE'] = os.path.join(os.getcwd(), 'no-such-workspace')
        self.addCleanup(env_patcher.stop)
        env_patcher.start()


    def test_download_fn(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the pull request
            mock_pull_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_pull_response.status = 200
            mock_pull_response.read_chunked.return_value = [
                json.dumps({'status': 'success', 'completed': 1000, 'total': 2000}).encode('utf-8'),
            ]

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_pull_response

            # Create the ChatManager instance
            download_manager = DownloadManager(app, 'llm:7b')
            app.downloads['llm:7b'] = download_manager
            mock_thread.assert_called_once_with(
                target=DownloadManager.download_thread_fn,
                args=(download_manager, mock_pool_manager_instance)
            )
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            DownloadManager.download_thread_fn(download_manager, mock_pool_manager_instance)
            self.assertDictEqual(app.downloads, {})
            self.assertIsNone(app.download_error)
            self.assertEqual(download_manager.status, 'success')
            self.assertEqual(download_manager.completed, 1000)
            self.assertEqual(download_manager.total, 2000)
            mock_pull_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_download_fn_stop(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the pull request
            mock_pull_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_pull_response.status = 200
            mock_pull_response.read_chunked.return_value = [
                json.dumps({'status': 'success', 'completed': 1000, 'total': 2000}).encode('utf-8'),
            ]

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_pull_response

            # Create the ChatManager instance
            download_manager = DownloadManager(app, 'llm:7b')
            download_manager.stop = True
            mock_thread.assert_called_once_with(
                target=DownloadManager.download_thread_fn,
                args=(download_manager, mock_pool_manager_instance)
            )
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            DownloadManager.download_thread_fn(download_manager, mock_pool_manager_instance)
            self.assertDictEqual(app.downloads, {})
            self.assertIsNone(app.download_error)
            self.assertEqual(download_manager.status, '')
            self.assertEqual(download_manager.completed, 0)
            self.assertEqual(download_manager.total, 0)
            mock_pull_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_download_fn_ollama_failure(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the pull request
            mock_pull_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_pull_response.status = 500

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_pull_response

            # Create the ChatManager instance
            download_manager = DownloadManager(app, 'llm:7b')
            app.downloads['llm:7b'] = download_manager
            mock_thread.assert_called_once_with(
                target=DownloadManager.download_thread_fn,
                args=(download_manager, mock_pool_manager_instance)
            )
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            DownloadManager.download_thread_fn(download_manager, mock_pool_manager_instance)
            self.assertDictEqual(app.downloads, {})
            self.assertEqual(app.download_error, 'Unknown model "llm:7b" (500)')
            self.assertEqual(download_manager.status, '')
            self.assertEqual(download_manager.completed, 0)
            self.assertEqual(download_manager.total, 0)
            mock_pull_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_download_fn_ollama_stream_error(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Out-of-date Ollama streams an error object after "pulling manifest"
            mock_pull_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_pull_response.status = 200
            mock_pull_response.read_chunked.return_value = [
                json.dumps({'status': 'pulling manifest'}).encode('utf-8'),
                json.dumps({
                    'error': 'pull model manifest: 412: The model you are attempting to pull requires a newer version of Ollama.'
                }).encode('utf-8'),
            ]

            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_pull_response

            download_manager = DownloadManager(app, 'llm:7b')
            app.downloads['llm:7b'] = download_manager
            mock_thread.assert_called_once_with(
                target=DownloadManager.download_thread_fn,
                args=(download_manager, mock_pool_manager_instance)
            )
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            DownloadManager.download_thread_fn(download_manager, mock_pool_manager_instance)
            self.assertDictEqual(app.downloads, {})
            self.assertEqual(
                app.download_error,
                'pull model manifest: 412: The model you are attempting to pull requires a newer version of Ollama.'
            )
            self.assertEqual(download_manager.status, 'pulling manifest')
            mock_pull_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


class TestAPI(unittest.TestCase):

    def test_xorigin(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path, xorigin=True)

            status, headers, content_bytes = app.request('GET', '/getConversations')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json'), ('Access-Control-Allow-Origin', '*')])
            self.assertDictEqual(response, {'workspace': temp_dir, 'conversations': [], 'templates': [], 'tasks': []})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_get_conversations(self):
        test_files = [
            ('ollama-chat.json', json.dumps({'model': 'llm', 'conversations': []}))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            status, headers, content_bytes = app.request('GET', '/getConversations')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual( \
                response, \
                {'workspace': temp_dir, 'model': 'llm', 'conversations': [], 'templates': [], 'tasks': []} \
            )

            # Verify the app config
            expected_config = {'model': 'llm', 'conversations': []}
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertDictEqual(json.load(config_fh), expected_config)


    def test_get_conversations_no_model(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            status, headers, content_bytes = app.request('GET', '/getConversations')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'workspace': temp_dir, 'conversations': [], 'templates': [], 'tasks': []})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_set_workspace(self):
        with unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': 'default-workspace'}):
            with create_test_files([]) as temp_dir:
                config_path = os.path.join(temp_dir, 'ollama-chat.json')
                app = OllamaChat(config_path)
                workspace = os.path.join(temp_dir, 'my-workspace')

                status, headers, content_bytes = app.request( \
                    'POST', '/setWorkspace', wsgi_input=json.dumps({'path': workspace}).encode('utf-8') \
                )
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '200 OK')
                self.assertListEqual(headers, [('Content-Type', 'application/json')])
                self.assertDictEqual(response, {'workspace': workspace})

                # The workspace and its memory files are created, and the config file is updated
                self.assertTrue(os.path.isfile(os.path.join(workspace, 'memory', 'USER.md')))
                self.assertTrue(os.path.isfile(os.path.join(workspace, 'memory', 'MEMORY.md')))
                self.assertTrue(os.path.exists(workspace))

                expected_config = {'workspace': workspace, 'conversations': []}
                with app.config() as config:
                    self.assertDictEqual(config, expected_config)
                with open(config_path, 'r', encoding='utf-8') as config_fh:
                    self.assertDictEqual(json.load(config_fh), expected_config)

                # The workspace is used for the memory files
                from ollama_chat.memory import read_memory_file  # pylint: disable=import-outside-toplevel
                self.assertIn('# Memory', read_memory_file(workspace, 'MEMORY.md'))


    def test_set_workspace_test(self):
        # A relative workspace path resolves to an absolute path
        with create_test_files([]) as temp_dir:
            old_cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                config_path = os.path.join(temp_dir, 'ollama-chat.json')
                app = OllamaChat(config_path)

                status, headers, content_bytes = app.request( \
                    'POST', '/setWorkspace', wsgi_input=json.dumps({'path': 'relative-ws'}).encode('utf-8') \
                )
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '200 OK')
                self.assertListEqual(headers, [('Content-Type', 'application/json')])
                self.assertDictEqual(response, {'workspace': os.path.join(temp_dir, 'relative-ws')})
            finally:
                os.chdir(old_cwd)


    def test_set_workspace_bad(self):
        # Unwritable workspace paths return an error
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            bad_path = os.path.join(temp_dir, 'blocked-ws')

            with unittest.mock.patch('ollama_chat.app.ensure_workspace', side_effect=OSError('permission denied')):
                status, headers, content_bytes = app.request( \
                    'POST', '/setWorkspace', wsgi_input=json.dumps({'path': bad_path}).encode('utf-8') \
                )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['error'], 'BadWorkspace')


    def test_get_settings(self):
        with unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': 'default-workspace'}):
            with create_test_files([]) as temp_dir:
                config_path = os.path.join(temp_dir, 'ollama-chat.json')
                app = OllamaChat(config_path)
                status, _headers, content_bytes = app.request('GET', '/getSettings')
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '200 OK')
                self.assertEqual(response['workspace'], 'default-workspace')
                self.assertDictEqual( \
                    response['email'], \
                    {'imapHost': '', 'imapPort': 993, 'smtpHost': '', 'smtpPort': 465, 'user': '', 'hasPassword': False}
                )


    def test_get_profile(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            app.request('POST', '/setWorkspace', wsgi_input=json.dumps({'path': os.path.join(temp_dir, 'ws')}).encode('utf-8'))
            status, _headers, content_bytes = app.request('GET', '/getProfile')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertEqual(response['limit'], 1500)
            self.assertTrue(response['content'].startswith('# About the user'))


    def test_set_profile(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            workspace_d = os.path.join(temp_dir, 'ws')
            app.request('POST', '/setWorkspace', wsgi_input=json.dumps({'path': workspace_d}).encode('utf-8'))

            # A profile save goes to memory/USER.md in the workspace - never into the config
            profile_content = '# About the user\n\n- Name: Oleg\n'
            status, _headers, content_bytes = app.request( \
                'POST', '/setProfile', wsgi_input=json.dumps({'content': profile_content}).encode('utf-8') \
            )
            self.assertEqual(status, '200 OK')
            self.assertEqual(json.loads(content_bytes.decode('utf-8')), {'saved': True})
            with open(os.path.join(workspace_d, 'memory', 'USER.md'), 'r', encoding='utf-8') as profile_fh:
                self.assertEqual(profile_fh.read(), profile_content)

            # A profile read gets the saved content
            status, _headers, content_bytes = app.request('GET', '/getProfile')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['content'], profile_content)

            # Content over the (default) limit is rejected
            status, _headers, content_bytes = app.request( \
                'POST', '/setProfile', wsgi_input=json.dumps({'content': 'x' * 1501}).encode('utf-8') \
            )
            self.assertEqual(json.loads(content_bytes.decode('utf-8'))['error'], 'ProfileTooLong')
            with open(os.path.join(workspace_d, 'memory', 'USER.md'), 'r', encoding='utf-8') as profile_fh:
                self.assertEqual(profile_fh.read(), profile_content)


    def test_set_profile_limit(self):
        test_files = [
            ('ollama-chat.json', json.dumps({'conversations': [], 'profileLimit': 100}))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            workspace_d = os.path.join(temp_dir, 'ws')
            app.request('POST', '/setWorkspace', wsgi_input=json.dumps({'path': workspace_d}).encode('utf-8'))

            # The profileLimit from the config is used
            _status, _headers, content_bytes = app.request('GET', '/getProfile')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['limit'], 100)

            # Content over the limit is rejected
            status, _headers, content_bytes = app.request( \
                'POST', '/setProfile', wsgi_input=json.dumps({'content': 'x' * 101}).encode('utf-8') \
            )
            self.assertEqual(json.loads(content_bytes.decode('utf-8'))['error'], 'ProfileTooLong')


    def test_set_email_settings(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            workspace_d = os.path.join(temp_dir, 'ws')
            app.request('POST', '/setWorkspace', wsgi_input=json.dumps({'path': workspace_d}).encode('utf-8'))

            status, _headers, content_bytes = app.request( \
                'POST', '/setEmailSettings', \
                wsgi_input=json.dumps({ \
                    'imapHost': 'imap.gmail.com', 'imapPort': 993, \
                    'smtpHost': 'smtp.gmail.com', 'smtpPort': 465, \
                    'user': 'me@gmail.com', 'password': 'app-password' \
                }).encode('utf-8') \
            )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertDictEqual(response, {'saved': True})

            # The .env file holds the password - the ollama-chat.json config never does
            with open(os.path.join(workspace_d, '.env'), 'r', encoding='utf-8') as env_fh:
                env_content = env_fh.read()
            self.assertIn('EMAIL_PASSWORD=app-password', env_content)
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertNotIn('app-password', config_fh.read())

            # A settings read never includes the password - just hasPassword
            status, _headers, content_bytes = app.request('GET', '/getSettings')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['email']['hasPassword'], True)
            self.assertNotIn('app-password', json.dumps(response))
            self.assertEqual(response['email']['user'], 'me@gmail.com')

            # An empty password keeps the saved password
            app.request( \
                'POST', '/setEmailSettings', \
                wsgi_input=json.dumps({ \
                    'imapHost': 'imap.gmail.com', 'imapPort': 993, \
                    'smtpHost': 'smtp.gmail.com', 'smtpPort': 465, 'user': 'me@gmail.com' \
                }).encode('utf-8') \
            )
            with open(os.path.join(workspace_d, '.env'), 'r', encoding='utf-8') as env_fh:
                self.assertIn('EMAIL_PASSWORD=app-password', env_fh.read())


    def test_test_email_connection(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            with unittest.mock.patch('ollama_chat.app.test_email_connection', return_value='IMAP: logged in to imap.example.com:993'):
                status, _headers, content_bytes = app.request('POST', '/testEmailConnection')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertDictEqual(response, {'message': 'IMAP: logged in to imap.example.com:993'})

            with unittest.mock.patch( \
                'ollama_chat.app.test_email_connection', \
                side_effect=ValueError('IMAP: cannot connect to the IMAP server "imap.example.com:993"') \
            ):
                status, _headers, content_bytes = app.request('POST', '/testEmailConnection')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'TestFailed')


    def test_set_task(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            request = {
                'name': 'Morning briefing',
                'time': '9:00',
                'days': [1, 2, 3, 4, 5],
                'model': 'llama3.2',
                'prompt': 'Make a report',
                'tools': ['web_search', 'fetch_page']
            }

            # Creating a task starts the scheduler thread
            with unittest.mock.patch('threading.Thread') as mock_thread:
                status, _headers, content_bytes = app.request( \
                    'POST', '/setTask', wsgi_input=json.dumps(request).encode('utf-8') \
                )
            mock_thread.assert_called_once()  # the scheduler thread starts lazily
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertEqual(response, {'id': 'morning-briefing'})
            with open(os.path.join(temp_dir, 'tasks.json'), 'r', encoding='utf-8') as tasks_fh:
                task = json.load(tasks_fh)[0]
            self.assertEqual(task['time'], '09:00')
            self.assertListEqual(task['tools'], ['web_search', 'fetch_page'])
            self.assertTrue(task.get('enabled', True))

            # Update the task
            request['id'] = 'morning-briefing'
            request['enabled'] = False
            status, _headers, content_bytes = app.request( \
                'POST', '/setTask', wsgi_input=json.dumps(request).encode('utf-8') \
            )
            self.assertEqual(status, '200 OK')
            with open(os.path.join(temp_dir, 'tasks.json'), 'r', encoding='utf-8') as tasks_fh:
                self.assertFalse(json.load(tasks_fh)[0]['enabled'])


    def test_set_task_errors(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            bad_requests = [
                {'name': 'Bad time', 'time': '25:00', 'days': [1], 'model': 'llm', 'prompt': 'p', 'tools': []},
                {'name': 'Bad days', 'time': '09:00', 'days': [8], 'model': 'llm', 'prompt': 'p', 'tools': []},
                {'name': 'Unknown task', 'id': 'nope', 'time': '09:00', 'days': [1], 'model': 'llm', 'prompt': 'p', 'tools': []}
            ]
            for request in bad_requests:
                status, _headers, content_bytes = app.request( \
                    'POST', '/setTask', wsgi_input=json.dumps(request).encode('utf-8') \
                )
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '400 Bad Request')
                self.assertEqual(response['error'], 'BadTask')


    def test_get_tasks_and_delete_task(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            app.request( \
                'POST', '/setTask', \
                wsgi_input=json.dumps({ \
                    'name': 'T', 'time': '09:00', 'days': [1], 'model': 'llm', 'prompt': 'p', \
                    'numCtx': 4096, 'tools': ['web_search'] \
                }).encode('utf-8') \
            )

            status, _headers, content_bytes = app.request('GET', '/getTasks')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual( \
                response['tasks'], \
                [{
                    'id': 't', 'name': 'T', 'time': '09:00', 'days': [1], 'model': 'llm',
                    'prompt': 'p', 'numCtx': 4096, 'tools': ['web_search'], 'enabled': True
                }]
            )

            status, _headers, content_bytes = app.request( \
                'POST', '/deleteTask', wsgi_input=json.dumps({'id': 't'}).encode('utf-8') \
            )
            self.assertEqual(status, '200 OK')
            status, _headers, content_bytes = app.request( \
                'POST', '/deleteTask', wsgi_input=json.dumps({'id': 't'}).encode('utf-8') \
            )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownTaskID')


    def test_run_task(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            from ollama_chat.tasks import save_tasks  # pylint: disable=import-outside-toplevel
            save_tasks(temp_dir, [{
                'id': 't', 'name': 'T', 'time': '09:00', 'days': [1], 'prompt': 'p', 'model': 'llm',
                'num_ctx': None, 'tools': [], 'dest': 'daily', 'lastRun': None, 'lastError': None
            }])

            with unittest.mock.patch('threading.Thread') as mock_thread:
                status, _headers, content_bytes = app.request( \
                    'POST', '/runTask', wsgi_input=json.dumps({'id': 't'}).encode('utf-8') \
                )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertDictEqual(response, {'started': True})
            mock_thread.assert_called_once()
            # The background thread target is the task manager's run_task_by_id
            target = mock_thread.call_args.kwargs['target']
            self.assertEqual(target.__name__, 'run_task_by_id')
            self.assertEqual(target.__self__ is app.tasks, True)

            status, _headers, content_bytes = app.request( \
                'POST', '/runTask', wsgi_input=json.dumps({'id': 'nope'}).encode('utf-8') \
            )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownTaskID')


    def test_get_task_log(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            from ollama_chat.tasks import save_tasks  # pylint: disable=import-outside-toplevel
            save_tasks(temp_dir, [{
                'id': 't', 'name': 'T', 'time': '09:00', 'days': [1], 'prompt': 'p', 'model': 'llm',
                'num_ctx': None, 'tools': [], 'dest': 'daily', 'lastRun': None, 'lastError': None
            }])

            # No log entries -> an empty response
            status, _headers, content_bytes = app.request('GET', '/getTaskLog', \
                query_string=encode_query_string({'id': 't'}))
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            os.mkdir(os.path.join(temp_dir, 'logs'))
            with open(os.path.join(temp_dir, 'logs', '2026-02-03.log'), 'w', encoding='utf-8') as log_fh:
                log_fh.write('09:00 ERROR task "t": boom\n')

            status, _headers, content_bytes = app.request('GET', '/getTaskLog', \
                query_string=encode_query_string({'id': 't'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['log'], '2026-02-03 09:00 ERROR task "t": boom')

            status, _headers, content_bytes = app.request('GET', '/getTaskLog', \
                query_string=encode_query_string({'id': 'nope'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownTaskID')


    def test_get_task_report(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            from ollama_chat.tasks import save_tasks  # pylint: disable=import-outside-toplevel
            save_tasks(temp_dir, [{
                'id': 't', 'name': 'T', 'time': '09:00', 'days': [1], 'prompt': 'p', 'model': 'llm',
                'num_ctx': None, 'tools': [], 'dest': 'daily', 'lastRun': None, 'lastError': None
            }])

            # No report yet -> an empty response
            status, _headers, content_bytes = app.request('GET', '/getTaskReport', \
                query_string=encode_query_string({'id': 't'}))
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            os.makedirs(os.path.join(temp_dir, 'memory', 'daily'))
            with open(os.path.join(temp_dir, 'memory', 'daily', '2026-02-03.md'), 'w', encoding='utf-8') as md_fh:
                md_fh.write('## T (09:00)\n\nThe report.\n')

            status, _headers, content_bytes = app.request('GET', '/getTaskReport', \
                query_string=encode_query_string({'id': 't'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response, {'date': '2026-02-03', 'report': '## T (09:00)\n\nThe report.'})

            status, _headers, content_bytes = app.request('GET', '/getTaskReport', \
                query_string=encode_query_string({'id': 'nope'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertEqual(response['error'], 'UnknownTaskID')


    def test_set_model(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            status, headers, content_bytes = app.request('POST', '/setModel', wsgi_input=json.dumps({'model': 'llm'}).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {})

            # Verify the app config
            expected_config = {'model': 'llm', 'conversations': []}
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_move_conversation_down(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                    {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []},
                    {'id': 'conv3', 'model': 'llm', 'title': 'Conversation 3', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move conv2 down
            status, headers, content_bytes = app.request(
                'POST', '/moveConversation', wsgi_input=json.dumps({'id': 'conv2', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                    {'id': 'conv3', 'model': 'llm', 'title': 'Conversation 3', 'exchanges': []},
                    {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_move_conversation_up(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                    {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []},
                    {'id': 'conv3', 'model': 'llm', 'title': 'Conversation 3', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move conv2 up
            status, headers, content_bytes = app.request(
                'POST', '/moveConversation', wsgi_input=json.dumps({'id': 'conv2', 'down': False}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []},
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                    {'id': 'conv3', 'model': 'llm', 'title': 'Conversation 3', 'exchanges': []}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_move_conversation_down_last(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []},
                {'id': 'conv3', 'model': 'llm', 'title': 'Conversation 3', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move conv3 down
            status, headers, content_bytes = app.request(
                'POST', '/moveConversation', wsgi_input=json.dumps({'id': 'conv3', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_move_conversation_up_first(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []},
                {'id': 'conv3', 'model': 'llm', 'title': 'Conversation 3', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move conv1 up
            status, headers, content_bytes = app.request(
                'POST', '/moveConversation', wsgi_input=json.dumps({'id': 'conv1', 'down': False}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_move_conversation_unknown_id(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to move a non-existent conversation
            status, headers, content_bytes = app.request(
                'POST', '/moveConversation', wsgi_input=json.dumps({'id': 'conv2', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_move_template_down(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [],
                'templates': [
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []},
                    {'id': 'tmpl3', 'title': 'Template 3', 'prompts': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move tmpl2 down
            status, headers, content_bytes = app.request(
                'POST', '/moveTemplate', wsgi_input=json.dumps({'id': 'tmpl2', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                    {'id': 'tmpl3', 'title': 'Template 3', 'prompts': []},
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_move_template_up(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [],
                'templates': [
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []},
                    {'id': 'tmpl3', 'title': 'Template 3', 'prompts': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move tmpl2 up
            status, headers, content_bytes = app.request(
                'POST', '/moveTemplate', wsgi_input=json.dumps({'id': 'tmpl2', 'down': False}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []},
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                    {'id': 'tmpl3', 'title': 'Template 3', 'prompts': []}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_move_template_down_last(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []},
                {'id': 'tmpl3', 'title': 'Template 3', 'prompts': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move tmpl3 down
            status, headers, content_bytes = app.request(
                'POST', '/moveTemplate', wsgi_input=json.dumps({'id': 'tmpl3', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_move_template_up_first(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []},
                {'id': 'tmpl3', 'title': 'Template 3', 'prompts': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Move tmpl1 up
            status, headers, content_bytes = app.request(
                'POST', '/moveTemplate', wsgi_input=json.dumps({'id': 'tmpl1', 'down': False}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_move_template_unknown_id(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to move tmpl2
            status, headers, content_bytes = app.request(
                'POST', '/moveTemplate', wsgi_input=json.dumps({'id': 'tmpl2', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_move_template_no_templates(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to move when templates key doesn't exist
            status, headers, content_bytes = app.request(
                'POST', '/moveTemplate', wsgi_input=json.dumps({'id': 'tmpl1', 'down': True}).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_template_success(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [],
                'templates': [
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []},
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Delete template 'tmpl1'
            status, headers, content_bytes = app.request(
                'POST', '/deleteTemplate', wsgi_input=json.dumps({'id': 'tmpl1'}).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': []}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_delete_template_unknown_id(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to delete 'tmpl2'
            status, headers, content_bytes = app.request(
                'POST', '/deleteTemplate', wsgi_input=json.dumps({'id': 'tmpl2'}).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_template_no_templates(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to delete when templates key doesn't exist
            status, headers, content_bytes = app.request(
                'POST', '/deleteTemplate', wsgi_input=json.dumps({'id': 'tmpl1'}).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_template_success(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']},
                {'id': 'tmpl2', 'title': 'Template 2', 'prompts': ['Prompt 2']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Get template 'tmpl1'
            status, headers, content_bytes = app.request(
                'GET', '/getTemplate', query_string=encode_query_string({'id': 'tmpl1'})
            )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(
                response,
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            )

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_template_unknown_id(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to get non-existent template 'tmpl2'
            status, headers, content_bytes = app.request(
                'GET', '/getTemplate', query_string=encode_query_string({'id': 'tmpl2'})
            )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_template_no_templates(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to get template when no templates exist
            status, headers, content_bytes = app.request(
                'GET', '/getTemplate', query_string=encode_query_string({'id': 'tmpl1'})
            )
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_update_template_success(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']},
                {'id': 'tmpl2', 'title': 'Template 2', 'prompts': ['Prompt 2']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Update template 'tmpl1'
            updated_template = {
                'id': 'tmpl1',
                'title': 'Updated Template 1',
                'prompts': ['Updated Prompt'],
                'variables': [{'name': 'var1', 'label': 'Variable 1'}]
            }
            status, headers, content_bytes = app.request(
                'POST', '/updateTemplate',
                wsgi_input=json.dumps(updated_template).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    updated_template,
                    {'id': 'tmpl2', 'title': 'Template 2', 'prompts': ['Prompt 2']}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_update_template_unknown_id(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update non-existent template 'tmpl2'
            updated_template = {'id': 'tmpl2', 'title': 'Updated Template 2', 'prompts': ['New Prompt']}
            status, headers, content_bytes = app.request(
                'POST', '/updateTemplate',
                wsgi_input=json.dumps(updated_template).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_update_template_no_templates(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            updated_template = {'id': 'tmpl1', 'title': 'New Template', 'prompts': ['New Prompt']}
            status, headers, content_bytes = app.request(
                'POST', '/updateTemplate',
                wsgi_input=json.dumps(updated_template).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_conversation(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'user': 'Hello'}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], ['Hello'], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['12345678-1234-5678-1234-567812345678'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                'model': 'llm',
                'conversations': [
                    {'id': '12345678-1234-5678-1234-567812345678', 'model': 'llm', 'title': 'Hello', 'exchanges': []}
                ]
            })

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_conversation_search(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Start a conversation with thinking and web search enabled
            request = {'user': 'Hello', 'think': True, 'search': True}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            mock_manager.assert_called_once_with(app, response['id'], ['Hello'], think=True, files=None, search=True, email=False)


    def test_start_conversation_model(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'model': 'llm', 'user': 'Hello'}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], ['Hello'], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['12345678-1234-5678-1234-567812345678'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                    'conversations': [
                        {'id': '12345678-1234-5678-1234-567812345678', 'model': 'llm', 'title': 'Hello', 'exchanges': []}
                    ]
                })

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_start_conversation_max_title(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            prompt = 'This is a very long title and needs to be cut off because its too long'
            request = {'model': 'llm', 'user': prompt}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], [prompt], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['12345678-1234-5678-1234-567812345678'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                    'conversations': [
                        {
                            'id': '12345678-1234-5678-1234-567812345678',
                            'model': 'llm',
                            'title': 'This is a very long title and needs to be cut o...',
                            'exchanges': []
                        }
                    ]
                })

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_start_conversation_no_model(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'user': 'Hello'}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'NoModel'})
            mock_manager.assert_not_called()
            self.assertNotIn('12345678-1234-5678-1234-567812345678', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_start_conversation_files(self):
        test_files = [
            ('ollama-chat.json', json.dumps({'model': 'llm', 'conversations': []}))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            files = [{'name': f'file{ix}.txt', 'type': 'text/plain', 'data': 'hello'} for ix in range(10)]

            # Attach the maximum number of files
            request = {'user': 'Hello', 'files': files}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], ['Hello'], think=False, files=files, search=False, email=False)
            mock_manager.reset_mock()

            # Attach one file too many
            request = {'user': 'Hello', 'files': files + [{'name': 'file10.txt', 'type': 'text/plain', 'data': 'hello'}]}
            status, headers, content_bytes = app.request('POST', '/startConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['error'], 'InvalidInput')
            self.assertEqual(response['member'], 'files')
            mock_manager.assert_not_called()


    def test_reply_conversation_files(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            files = [{'name': f'file{ix}.md', 'type': 'text/markdown', 'data': 'hello'} for ix in range(10)]

            # Reply with the maximum number of files
            request = {'id': 'conv1', 'user': 'How are you?', 'files': files}
            status, headers, content_bytes = app.request('POST', '/replyConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            mock_manager.assert_called_once_with(app, 'conv1', ['How are you?'], think=False, files=files, search=False, email=False)
            mock_manager.reset_mock()

            # Reply with one file too many
            request = {'id': 'conv1', 'user': 'How are you?', 'files': files + [{'name': 'file10.md', 'type': 'text/markdown', 'data': 'hello'}]}
            status, headers, content_bytes = app.request('POST', '/replyConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(response['error'], 'InvalidInput')
            self.assertEqual(response['member'], 'files')
            mock_manager.assert_not_called()


    def test_get_conversation_files(self):
        original_config = {
            'conversations': [
                {
                    'id': 'conv1',
                    'model': 'llm',
                    'title': 'Conversation 1',
                    'exchanges': [
                        {
                            'user': 'Hello',
                            'model': 'Hi there',
                            'files': [
                                {'name': 'a.txt', 'type': 'text/plain'},
                                {'name': 'b.png'}
                            ]
                        }
                    ]
                }
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # The stored file references are returned with the conversation
            status, headers, content_bytes = app.request('GET', '/getConversation', query_string=encode_query_string({'id': 'conv1'}))
            self.assertEqual(status, '200 OK')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertListEqual(
                response['conversation']['exchanges'][0]['files'],
                [{'name': 'a.txt', 'type': 'text/plain'}, {'name': 'b.png'}]
            )


    def test_start_template(self):
        original_config = {
            'model': 'llm',
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'id': 'tmpl1'}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], ['Prompt 1'], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['12345678-1234-5678-1234-567812345678'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                    'model': 'llm',
                    'conversations': [
                        {'id': '12345678-1234-5678-1234-567812345678', 'model': 'llm', 'title': 'Template 1', 'exchanges': []}
                    ],
                    'templates': [
                        {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
                    ]
                })

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_template_by_name(self):
        original_config = {
            'model': 'llm',
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'id': 'test'}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], ['Prompt 1'], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['12345678-1234-5678-1234-567812345678'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                    'model': 'llm',
                    'conversations': [
                        {'id': '12345678-1234-5678-1234-567812345678', 'model': 'llm', 'title': 'Template 1', 'exchanges': []}
                    ],
                    'templates': [
                        {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
                    ]
                })

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_template_model(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value = '12345678-1234-5678-1234-567812345678'), \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'model': 'llm', 'id': 'tmpl1'}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})
            mock_manager.assert_called_once_with(app, response['id'], ['Prompt 1'], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['12345678-1234-5678-1234-567812345678'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                    'conversations': [
                        {'id': '12345678-1234-5678-1234-567812345678', 'model': 'llm', 'title': 'Template 1', 'exchanges': []}
                    ],
                    'templates': [
                        {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
                    ]
                })

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_template_no_model(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'id': 'tmpl1'}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'NoModel'})
            mock_manager.assert_not_called()
            self.assertNotIn('12345678-1234-5678-1234-567812345678', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_template_unknown_template(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'id': 'unknown'}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownTemplateID', 'message': 'Unknown template "unknown"'})
            mock_manager.assert_not_called()
            self.assertNotIn('12345678-1234-5678-1234-567812345678', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_start_template_unknown_variable(self):
        original_config = {
            'conversations': [],
            'templates': [
                {'id': 'tmpl1', 'name': 'test', 'title': 'Template 1', 'prompts': ['Prompt 1']}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'id': 'tmpl1', 'variables': {'foo': 'bar'}}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownVariable', 'message': 'unknown variable "foo"'})
            mock_manager.assert_not_called()
            self.assertNotIn('12345678-1234-5678-1234-567812345678', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_start_template_missing_variable(self):
        original_config = {
            'conversations': [],
            'templates': [
                {
                    'id': 'tmpl1',
                    'name': 'test',
                    'title': 'Template 1',
                    'variables': [{'name': 'name', 'label': 'Name'}],
                    'prompts': ['Prompt {{name}}'],
                }
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to update template when no templates exist
            request = {'id': 'tmpl1'}
            status, headers, content_bytes = app.request('POST', '/startTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'MissingVariable', 'message': 'missing variable value for "name"'})
            mock_manager.assert_not_called()
            self.assertNotIn('12345678-1234-5678-1234-567812345678', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_stop_conversation_success(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock ChatManager instance
            mock_chat = unittest.mock.Mock()
            mock_chat.stop = False
            app.chats['conv1'] = mock_chat

            # Stop the conversation
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request('POST', '/stopConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            self.assertTrue(mock_chat.stop)
            self.assertNotIn('conv1', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_stop_conversation_unknown_id(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to stop non-existent conversation
            request = {'id': 'conv2'}
            status, headers, content_bytes = app.request('POST', '/stopConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})
            self.assertNotIn('conv2', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_stop_conversation_not_generating(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to stop conversation that's not generating
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request('POST', '/stopConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            self.assertDictEqual(app.chats, {})
            self.assertNotIn('conv1', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_conversation_success_not_generating(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Get conversation 'conv1'
            status, headers, content_bytes = app.request('GET', '/getConversation', query_string=encode_query_string({'id': 'conv1'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(
                response,
                {
                    'conversation': {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [{'user': 'Hello', 'model': 'Hi there'}],
                        'generating': False
                    }
                }
            )

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_conversation_success_generating(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Add a mock ChatManager to simulate generating state
            mock_chat = unittest.mock.Mock()
            app.chats['conv1'] = mock_chat

            # Get conversation 'conv1'
            status, headers, content_bytes = app.request('GET', '/getConversation', query_string=encode_query_string({'id': 'conv1'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(
                response,
                {
                    'conversation': {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [{'user': 'Hello', 'model': 'Hi there'}],
                        'generating': True
                    }
                }
            )

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_conversation_unknown_id(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to get non-existent conversation 'conv2'
            status, headers, content_bytes = app.request('GET', '/getConversation', query_string=encode_query_string({'id': 'conv2'}))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_export_pdf_conversation(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Привет, мир! Zażółć gęślą jaźń'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Export conversation 'conv1' as PDF
            status, headers, content_bytes = app.request('POST', '/exportPdf', wsgi_input=json.dumps({'id': 'conv1'}).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'file': os.path.join(temp_dir, 'exports', 'conversation-1.pdf')})

            # Exported PDF
            with open(response['file'], 'rb') as pdf_fh:
                self.assertTrue(pdf_fh.read().startswith(b'%PDF'))


    def test_export_pdf_conversation_unknown_id(self):
        with create_test_files([]) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to export a non-existent conversation
            status, headers, content_bytes = app.request('POST', '/exportPdf', wsgi_input=json.dumps({'id': 'conv2'}).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})


    def test_export_pdf_memory_file(self):
        test_files = [
            (['memory', 'USER.md'], '# About me\n\nПривет, мир! Zażółć gęślą jaźń.'),
            (['memory', 'MEMORY.md'], '- Note 1\n- Note 2'),
            (['memory', 'daily', '2026-01-15.md'], '## Утренний брифинг (09:00)\n\nNote A'),
            ('ollama-chat.json', json.dumps({'conversations': []}))
        ]
        with create_test_files(test_files) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Export each memory file as PDF
            pdf_files = [
                ('USER.md', 'user-md.pdf'),
                ('MEMORY.md', 'memory-md.pdf'),
                ('daily/2026-01-15.md', 'daily-2026-01-15-md.pdf')
            ]
            for file_name, pdf_filename in pdf_files:
                status, headers, content_bytes = app.request( \
                    'POST', '/exportPdf', wsgi_input=json.dumps({'file': file_name}).encode('utf-8') \
                )
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '200 OK')
                self.assertListEqual(headers, [('Content-Type', 'application/json')])
                self.assertEqual(response['file'], os.path.join(temp_dir, 'exports', pdf_filename))
                with open(response['file'], 'rb') as pdf_fh:
                    self.assertTrue(pdf_fh.read().startswith(b'%PDF'))


    def test_export_pdf_unknown_file(self):
        with create_test_files([]) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Unknown memory file, bad date, and no ID or file
            for request_body, message in [
                ({'file': 'SECRET.md'}, 'Unknown memory file "SECRET.md"'),
                ({'file': 'daily/2026-13-01.md'}, 'Unknown memory file "daily/2026-13-01.md"'),
                ({}, 'One of "id" or "file" must be specified')
            ]:
                status, headers, content_bytes = app.request('POST', '/exportPdf', wsgi_input=json.dumps(request_body).encode('utf-8'))
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '400 Bad Request')
                self.assertListEqual(headers, [('Content-Type', 'application/json')])
                # Note: memory-file paths outside memory/ are rejected by the daily/ regex
                self.assertEqual(response, {'error': 'UnknownFile', 'message': message})


    def test_send_email(self):
        original_config = {
            'conversations': [
                {
                    'id': 'conv1',
                    'model': 'llm',
                    'title': 'Conversation 1',
                    'exchanges': [
                        {
                            'user': 'Send my regards',
                            'model': 'The draft is ready.',
                            'email': {'to': 'client@example.com', 'subject': 'Regards', 'body': 'Kindest regards.'}
                        }
                    ]
                }
            ]
        }
        test_files = [('ollama-chat.json', json.dumps(original_config))]
        with create_test_files(test_files) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}), \
              unittest.mock.patch('ollama_chat.app.smtp_send_email', return_value='Email sent to client@example.com') as mock_send:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Send the drafted email
            status, headers, content_bytes = app.request('POST', '/sendEmail', wsgi_input=json.dumps({'id': 'conv1'}).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'sent': True})
            mock_send.assert_called_once_with('client@example.com', 'Regards', 'Kindest regards.')

            # The draft is marked as sent
            with app.config() as config:
                email_draft = config['conversations'][0]['exchanges'][0]['email']
                self.assertDictEqual(email_draft, {'to': 'client@example.com', 'subject': 'Regards', 'body': 'Kindest regards.', 'sent': True})


    def test_send_email_discard(self):
        original_config = {
            'conversations': [
                {
                    'id': 'conv1',
                    'model': 'llm',
                    'title': 'Conversation 1',
                    'exchanges': [
                        {
                            'user': 'Never mind',
                            'model': 'The draft is ready.',
                            'email': {'to': 'client@example.com', 'subject': 'Regards', 'body': 'Kindest regards.'}
                        }
                    ]
                }
            ]
        }
        test_files = [('ollama-chat.json', json.dumps(original_config))]
        with create_test_files(test_files) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}), \
              unittest.mock.patch('ollama_chat.app.smtp_send_email') as mock_send:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Discard the drafted email
            status, headers, content_bytes = app.request('POST', '/sendEmail', wsgi_input=json.dumps({'id': 'conv1', 'send': False}).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'sent': False})
            mock_send.assert_not_called()

            # The draft is gone and the change is saved
            with app.config() as config:
                self.assertNotIn('email', config['conversations'][0]['exchanges'][0])
            with open(config_path, encoding='utf-8') as config_fh:
                saved_config = json.load(config_fh)
            self.assertNotIn('email', saved_config['conversations'][0]['exchanges'][0])


    def test_send_email_errors(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi!'}]},
                {
                    'id': 'conv2',
                    'model': 'llm',
                    'title': 'Conversation 2',
                    'exchanges': [{'user': 'Hi', 'model': 'Hello', 'email': {'to': 'client@example.com', 'subject': 'Hi', 'body': 'Hello.'}}]
                }
            ]
        }
        test_files = [('ollama-chat.json', json.dumps(original_config))]
        with create_test_files(test_files) as temp_dir, \
              unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': temp_dir}), \
              unittest.mock.patch('ollama_chat.app.smtp_send_email', side_effect=ValueError('SMTP server is down')):
            app = OllamaChat(os.path.join(temp_dir, 'ollama-chat.json'))

            # Unknown conversation and no draft
            for request_body, error in [
                ({'id': 'conv3'}, 'UnknownConversationID'),
                ({'id': 'conv1'}, 'NoEmailDraft')
            ]:
                status, headers, content_bytes = app.request('POST', '/sendEmail', wsgi_input=json.dumps(request_body).encode('utf-8'))
                response = json.loads(content_bytes.decode('utf-8'))
                self.assertEqual(status, '400 Bad Request')
                self.assertListEqual(headers, [('Content-Type', 'application/json')])
                self.assertDictEqual(response, {'error': error})

            # Send failure
            status, headers, content_bytes = app.request('POST', '/sendEmail', wsgi_input=json.dumps({'id': 'conv2'}).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'error': 'SendFailed', 'message': 'SMTP server is down'})

            # The failed draft is kept so the user can retry
            with app.config() as config:
                self.assertIn('email', config['conversations'][1]['exchanges'][0])


    def test_reply_conversation_success(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Reply to conversation 'conv1'
            request = {'id': 'conv1', 'user': 'How are you?'}
            status, headers, content_bytes = app.request('POST', '/replyConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            mock_manager.assert_called_once_with(app, 'conv1', ['How are you?'], think=False, files=None, search=False, email=False)
            self.assertIs(app.chats['conv1'], mock_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_reply_conversation_search(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Reply to conversation 'conv1' with web search enabled
            request = {'id': 'conv1', 'user': 'How are you?', 'think': True, 'search': True}
            status, headers, content_bytes = app.request('POST', '/replyConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            mock_manager.assert_called_once_with(app, 'conv1', ['How are you?'], think=True, files=None, search=True, email=False)


    def test_reply_conversation_unknown_id(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to reply to non-existent conversation 'conv2'
            request = {'id': 'conv2', 'user': 'How are you?'}
            status, headers, content_bytes = app.request('POST', '/replyConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})
            mock_manager.assert_not_called()
            self.assertNotIn('conv2', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_reply_conversation_busy(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Simulate a busy conversation by adding it to chats
            mock_chat = unittest.mock.Mock()
            app.chats['conv1'] = mock_chat

            # Try to reply to busy conversation 'conv1'
            request = {'id': 'conv1', 'user': 'How are you?'}
            status, headers, content_bytes = app.request('POST', '/replyConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'ConversationBusy'})
            mock_manager.assert_not_called()
            self.assertEqual(app.chats['conv1'], mock_chat)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_set_conversation_title_success(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [{'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Set new title for conversation 'conv1'
            request = {'id': 'conv1', 'title': 'New Title'}
            status, headers, content_bytes = app.request('POST', '/setConversationTitle', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [{'id': 'conv1', 'model': 'llm', 'title': 'New Title', 'exchanges': []}]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_set_conversation_title_unknown_id(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to set title for non-existent conversation 'conv2'
            request = {'id': 'conv2', 'title': 'New Title'}
            status, headers, content_bytes = app.request('POST', '/setConversationTitle', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_set_conversation_title_busy(self):
        original_config = {
            'conversations': [{'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Simulate a busy conversation by adding it to chats
            mock_chat = unittest.mock.Mock()
            app.chats['conv1'] = mock_chat

            # Try to set title for busy conversation 'conv1'
            request = {'id': 'conv1', 'title': 'New Title'}
            status, headers, content_bytes = app.request('POST', '/setConversationTitle', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'ConversationBusy'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_conversation_success(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []},
                    {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Delete conversation 'conv1'
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request('POST', '/deleteConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv2', 'model': 'llm', 'title': 'Conversation 2', 'exchanges': []}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_delete_conversation_unknown_id(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to delete non-existent conversation 'conv2'
            request = {'id': 'conv2'}
            status, headers, content_bytes = app.request('POST', '/deleteConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_delete_conversation_busy(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Simulate a busy conversation by adding it to chats
            mock_chat = unittest.mock.Mock()
            app.chats['conv1'] = mock_chat

            # Try to delete busy conversation 'conv1'
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request('POST', '/deleteConversation', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'ConversationBusy'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_create_template_basic(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [],
                'templates': [
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('uuid.uuid4', return_value='12345678-1234-5678-1234-567812345678'):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a basic template
            request = {'title': 'New Template', 'prompts': ['New Prompt']}
            status, headers, content_bytes = app.request('POST', '/createTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    {'id': '12345678-1234-5678-1234-567812345678', 'title': 'New Template', 'prompts': ['New Prompt']},
                    {'id': 'tmpl1', 'title': 'Template 1', 'prompts': ['Prompt 1']}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_create_template_no_templates(self):
        with create_test_files([]) as temp_dir, \
        unittest.mock.patch('uuid.uuid4', return_value='12345678-1234-5678-1234-567812345678'):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a basic template
            request = {'title': 'New Template', 'prompts': ['New Prompt']}
            status, headers, content_bytes = app.request('POST', '/createTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    {'id': '12345678-1234-5678-1234-567812345678', 'title': 'New Template', 'prompts': ['New Prompt']}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_create_template_optional_arguments(self):
        with create_test_files([]) as temp_dir, \
        unittest.mock.patch('uuid.uuid4', return_value='12345678-1234-5678-1234-567812345678'):
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a template with all fields
            request = {
                'title': 'New Template',
                'prompts': ['New Prompt'],
                'name': 'test_template',
                'variables': [{'name': 'var1', 'label': 'Variable 1'}]
            }
            status, headers, content_bytes = app.request('POST', '/createTemplate', wsgi_input=json.dumps(request).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'id': '12345678-1234-5678-1234-567812345678'})

            # Verify the app config
            expected_config = {
                'conversations': [],
                'templates': [
                    {
                        'id': '12345678-1234-5678-1234-567812345678',
                        'title': 'New Template',
                        'prompts': ['New Prompt'],
                        'name': 'test_template',
                        'variables': [{'name': 'var1', 'label': 'Variable 1'}]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_delete_conversation_exchange_success(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {'user': 'Hello', 'model': 'Hi there'},
                            {'user': 'How are you?', 'model': 'Good'}
                        ]
                    }
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Delete the most recent exchange from 'conv1'
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request(
                'POST', '/deleteConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_delete_conversation_exchange_unknown_id(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to delete exchange from non-existent conversation 'conv2'
            request = {'id': 'conv2'}
            status, headers, content_bytes = app.request(
                'POST', '/deleteConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_conversation_exchange_busy(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Simulate a busy conversation
            mock_chat = unittest.mock.Mock()
            app.chats['conv1'] = mock_chat

            # Try to delete exchange from busy conversation 'conv1'
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request(
                'POST', '/deleteConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'ConversationBusy'})
            self.assertIs(app.chats['conv1'], mock_chat)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_conversation_exchange_empty(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to delete exchange from conversation with no exchanges
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request(
                'POST', '/deleteConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            self.assertNotIn('conv1', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_regenerate_conversation_exchange_success(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {'user': 'Hello', 'model': 'Hi there'},
                            {'user': 'How are you?', 'model': 'Good'}
                        ]
                    }
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Regenerate the last exchange for 'conv1'
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request(
                'POST', '/regenerateConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})

            # Check that ChatManager was called with the last user prompt
            mock_manager.assert_called_once_with(app, 'conv1', ['How are you?'])
            self.assertIs(app.chats['conv1'], mock_manager.return_value)

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_regenerate_conversation_exchange_unknown_id(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to regenerate exchange for non-existent conversation 'conv2'
            request = {'id': 'conv2'}
            status, headers, content_bytes = app.request(
                'POST', '/regenerateConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'UnknownConversationID'})
            mock_manager.assert_not_called()
            self.assertNotIn('conv2', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_regenerate_conversation_exchange_busy(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello', 'model': 'Hi there'}]}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Simulate a busy conversation
            mock_chat = unittest.mock.Mock()
            app.chats['conv1'] = mock_chat

            # Try to regenerate exchange for busy conversation 'conv1'
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request(
                'POST', '/regenerateConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '400 Bad Request')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'error': 'ConversationBusy'})
            mock_manager.assert_not_called()
            self.assertIs(app.chats['conv1'], mock_chat)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_regenerate_conversation_exchange_empty(self):
        original_config = {
            'conversations': [
                {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
            ]
        }
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.ChatManager') as mock_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to regenerate exchange for conversation with no exchanges
            request = {'id': 'conv1'}
            status, headers, content_bytes = app.request(
                'POST', '/regenerateConversationExchange', wsgi_input=json.dumps(request).encode('utf-8')
            )
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            mock_manager.assert_not_called()
            self.assertNotIn('conv1', app.chats)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_success(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
                ('ollama-chat.json', json.dumps(original_config))
             ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': [
                    {
                        'model': 'llm:7b',
                        'details': {'parameter_size': '7B'},
                        'size': 4100000000,
                        'modified_at': '2023-10-01T12:00:00+00:00'
                    },
                    {
                        'model': 'other:tag',
                        'details': {'parameter_size': '3M'},
                        'size': 1800000,
                        'modified_at': '2023-10-02T12:00:00+00:00'
                    },
                    {
                        'model': 'other2:tag',
                        'details': {'parameter_size': '3K'},
                        'size': 1800,
                        'modified_at': '2023-10-02T12:00:00+00:00'
                    },
                    {
                        'model': 'big:1t',
                        'details': {'parameter_size': '1t'},
                        'size': 5000000000,
                        'modified_at': '2023-10-03T12:00:00+00:00'
                    },
                    {
                        'model': 'big:756b',
                        'details': {'parameter_size': '756b'},
                        'size': 4000000000,
                        'modified_at': '2023-10-03T12:00:00+00:00'
                    }
                ]
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [
                    {
                        'id': 'big:1t', 'name': 'big', 'parameters': 1000000000000, 'size': 5000000000,
                        'modified': '2023-10-03T12:00:00+00:00'
                    },
                    {
                        'id': 'big:756b', 'name': 'big', 'parameters': 756000000000, 'size': 4000000000,
                        'modified': '2023-10-03T12:00:00+00:00'
                    },
                    {'id': 'llm:7b', 'name': 'llm', 'parameters': 7000000000, 'size': 4100000000, 'modified': '2023-10-01T12:00:00+00:00'},
                    {'id': 'other2:tag', 'modified': '2023-10-02T12:00:00+00:00', 'name': 'other2', 'parameters': 3000, 'size': 1800},
                    {'id': 'other:tag', 'name': 'other', 'parameters': 3000000, 'size': 1800000, 'modified': '2023-10-02T12:00:00+00:00'}
                ],
                'downloading': [],
                'model': 'llm'
            })
            mock_list_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_no_tag(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # A model id with no ":" tag
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': [
                    {
                        'model': 'tagless',
                        'details': {'parameter_size': '7B'},
                        'size': 4100000000,
                        'modified_at': '2023-10-01T12:00:00+00:00'
                    }
                ]
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [
                    {
                        'id': 'tagless',
                        'name': 'tagless',
                        'parameters': 7000000000,
                        'size': 4100000000,
                        'modified': '2023-10-01T12:00:00+00:00'
                    }
                ],
                'downloading': []
            })
            mock_list_response.close.assert_called_once_with()


    def test_get_models_parameter_size_warning(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
                ('ollama-chat.json', json.dumps(original_config))
             ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': [
                    {
                        'model': 'llm:7b',
                        'details': {'parameter_size': '1000'},
                        'size': 1000,
                        'modified_at': '2023-10-01T12:00:00+00:00'
                    }
                ]
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            environ = {'wsgi.errors': StringIO()}
            status, headers, content_bytes = app.request('GET', '/getModels', environ=environ)
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [
                    {'id': 'llm:7b', 'name': 'llm', 'parameters': 0, 'size': 1000, 'modified': '2023-10-01T12:00:00+00:00'}
                ],
                'downloading': [],
                'model': 'llm'
            })
            mock_list_response.close.assert_called_once_with()
            logs = environ['wsgi.errors'].getvalue()
            logs = re.sub(r'\[.*?\]', '[X / Y]', logs)
            self.assertEqual(logs, 'WARNING [X / Y] Invalid parameter size "1000"\n')

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_parameter_size_invalid(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
                ('ollama-chat.json', json.dumps(original_config))
             ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request (parameter size fails to parse)
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': [
                    {
                        'model': 'llm:7b',
                        'details': {'parameter_size': 'abcB'},
                        'size': 1000,
                        'modified_at': '2023-10-01T12:00:00+00:00'
                    }
                ]
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            environ = {'wsgi.errors': StringIO()}
            status, headers, content_bytes = app.request('GET', '/getModels', environ=environ)
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [
                    {'id': 'llm:7b', 'name': 'llm', 'parameters': 0, 'size': 1000, 'modified': '2023-10-01T12:00:00+00:00'}
                ],
                'downloading': [],
                'model': 'llm'
            })
            mock_list_response.close.assert_called_once_with()
            logs = environ['wsgi.errors'].getvalue()
            logs = re.sub(r'\[.*?\]', '[X / Y]', logs)
            self.assertEqual(logs, 'WARNING [X / Y] Invalid parameter size "abcB"\n')

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_parameter_size_empty(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
                ('ollama-chat.json', json.dumps(original_config))
             ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': [
                    {
                        'model': 'llm:7b',
                        'details': {'parameter_size': ''},
                        'size': 1000,
                        'modified_at': '2023-10-01T12:00:00+00:00'
                    }
                ]
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            environ = {'wsgi.errors': StringIO()}
            status, headers, content_bytes = app.request('GET', '/getModels', environ=environ)
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [
                    {'id': 'llm:7b', 'name': 'llm', 'parameters': 0, 'size': 1000, 'modified': '2023-10-01T12:00:00+00:00'}
                ],
                'downloading': [],
                'model': 'llm'
            })
            mock_list_response.close.assert_called_once_with()
            # An empty parameter size (MLX models) is a known case - no warning is logged
            logs = environ['wsgi.errors'].getvalue()
            self.assertEqual(logs, '')

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_no_models(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': []
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'models': [], 'downloading': [], 'model': 'llm'})
            mock_list_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_downloading(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {'models': []}

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            # Add downloading models
            mock_download = unittest.mock.Mock()
            mock_download.status = 'downloading'
            mock_download.completed = 5000000
            mock_download.total = 10000000
            app.downloads['downloading_model'] = mock_download
            mock_download2 = unittest.mock.Mock()
            mock_download2.status = 'unknown'
            mock_download2.completed = 0
            mock_download2.total = 0
            app.downloads['downloading_model2'] = mock_download2

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [],
                'downloading': [
                    {'id': 'downloading_model', 'status': 'downloading', 'completed': 5000000, 'size': 10000000},
                    {'id': 'downloading_model2', 'status': 'unknown', 'completed': 0}
                ],
                'model': 'llm'
            })
            mock_list_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_download_error(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            app.download_error = 'pull model manifest: 412: requires a newer version of Ollama.'

            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {'models': []}

            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [],
                'downloading': [],
                'model': 'llm',
                'downloadError': 'pull model manifest: 412: requires a newer version of Ollama.'
            })
            self.assertIsNone(app.download_error)
            mock_list_response.close.assert_called_once_with()

            # A subsequent getModels omits the consumed error
            mock_list_response.json.return_value = {'models': []}
            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertDictEqual(response, {
                'models': [],
                'downloading': [],
                'model': 'llm'
            })
            self.assertIsNone(app.download_error)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_ollama_failure(self):
        original_config = {'model': 'llm', 'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 500

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '500 Internal Server Error')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {'error': 'UnexpectedError'})
            mock_list_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_models_no_config_model(self):
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the list request
            mock_list_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_list_response.status = 200
            mock_list_response.json.return_value = {
                'models': [
                    {
                        'model': 'llm:7b',
                        'details': {'parameter_size': '7B'},
                        'size': 4100000000,
                        'modified_at': '2023-10-01T12:00:00+00:00'
                    }
                ]
            }

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_list_response

            status, headers, content_bytes = app.request('GET', '/getModels')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {
                'models': [
                    {'id': 'llm:7b', 'name': 'llm', 'parameters': 7000000000, 'size': 4100000000, 'modified': '2023-10-01T12:00:00+00:00'}
                ],
                'downloading': []
            })
            mock_list_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_download_model_success(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.DownloadManager') as mock_download_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Initiate model download
            request = {'model': 'llm:7b'}
            status, headers, content_bytes = app.request('POST', '/downloadModel', wsgi_input=json.dumps(request).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {})

            # Verify DownloadManager was called and stored
            mock_download_manager.assert_called_once_with(app, 'llm:7b')
            self.assertIn('llm:7b', app.downloads)
            self.assertIs(app.downloads['llm:7b'], mock_download_manager.return_value)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_download_model_already_downloading(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('ollama_chat.app.DownloadManager') as mock_download_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # A download is already in progress for the model
            existing_manager = unittest.mock.Mock()
            app.downloads['llm:7b'] = existing_manager

            # Initiate a duplicate model download
            request = {'model': 'llm:7b'}
            status, headers, content_bytes = app.request('POST', '/downloadModel', wsgi_input=json.dumps(request).encode('utf-8'))
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(response, {})

            # Verify no new DownloadManager was created and the in-flight download is untouched
            mock_download_manager.assert_not_called()
            self.assertIs(app.downloads['llm:7b'], existing_manager)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)


    def test_stop_model_download_success(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Add a mock download to the downloads dictionary
            mock_download = unittest.mock.Mock()
            mock_download.stop = False
            app.downloads['llm:7b'] = mock_download

            # Stop the model download
            request = {'model': 'llm:7b'}
            status, headers, content_bytes = app.request('POST', '/stopModelDownload', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            self.assertTrue(mock_download.stop)  # Verify stop flag was set
            self.assertIs(app.downloads['llm:7b'], mock_download)

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_stop_model_download_not_downloading(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Try to stop a non-existent download
            request = {'model': 'llm:7b'}
            status, headers, content_bytes = app.request('POST', '/stopModelDownload', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            self.assertDictEqual(app.downloads, {})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_model_success(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the delete request
            mock_delete_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_delete_response.status = 200

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_delete_response

            # Delete model 'llm:7b'
            request = {'model': 'llm:7b'}
            status, headers, content_bytes = app.request('POST', '/deleteModel', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {})
            mock_pool_manager_instance.request.assert_called_once_with(
                'DELETE', 'http://127.0.0.1:11434/api/delete', json={'model': 'llm:7b'}, retries=0
            )
            mock_delete_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_delete_model_error(self):
        original_config = {'conversations': []}
        test_files = [
            ('ollama-chat.json', json.dumps(original_config))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Create a mock Response object for the delete request
            mock_delete_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_delete_response.status = 500

            # Configure the mock PoolManager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_delete_response

            # Delete model 'llm:7b'
            request = {'model': 'llm:7b'}
            status, headers, content_bytes = app.request('POST', '/deleteModel', wsgi_input=json.dumps(request).encode('utf-8'))
            self.assertEqual(status, '500 Internal Server Error')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertDictEqual(json.loads(content_bytes.decode('utf-8')), {'error': 'UnexpectedError'})
            mock_pool_manager_instance.request.assert_called_once_with(
                'DELETE', 'http://127.0.0.1:11434/api/delete', json={'model': 'llm:7b'}, retries=0
            )
            mock_delete_response.close.assert_called_once_with()

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, original_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), original_config)


    def test_get_system_info(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Make the request
            status, headers, content_bytes = app.request('GET', '/getSystemInfo')
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            self.assertTrue(response['memory'] > 0)
            self.assertIsInstance(response['mlx'], bool)
            del response['memory']
            del response['mlx']
            self.assertDictEqual(response, {})

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {'conversations': []})

            # Verify the config file
            self.assertFalse(os.path.exists(config_path))


    def test_get_system_info_unknown_memory(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # os.sysconf returns -1 when the total memory is indeterminate; the action reports memory as -1.
            # Force the non-Windows branch and create os.sysconf (absent on Windows) so the test runs cross-platform.
            with unittest.mock.patch('platform.system', return_value='Linux'), \
                    unittest.mock.patch('os.sysconf', return_value=-1, create=True):
                status, headers, content_bytes = app.request('GET', '/getSystemInfo')
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'memory': -1, 'mlx': False})


    def test_get_system_info_mlx(self):
        with create_test_files([]) as temp_dir:
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)

            # Force the Apple Silicon platform (and the non-Windows memory branch) so the test runs cross-platform
            with unittest.mock.patch('platform.system', return_value='Darwin'), \
                    unittest.mock.patch('platform.machine', return_value='arm64'), \
                    unittest.mock.patch('os.sysconf', return_value=65536, create=True):
                status, headers, content_bytes = app.request('GET', '/getSystemInfo')
            self.assertEqual(status, '200 OK')
            self.assertListEqual(headers, [('Content-Type', 'application/json')])
            response = json.loads(content_bytes.decode('utf-8'))
            self.assertDictEqual(response, {'memory': 65536 * 65536, 'mlx': True})
