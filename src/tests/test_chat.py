# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import base64
import copy
import io
import json
import os
import pathlib
import unittest
import unittest.mock

import docx
import urllib3

from ollama_chat.app import OllamaChat
from ollama_chat.chat import (
    _escape_markdown_text, _process_commands, _run_tool, _tool_call_arguments, config_template_prompts, ChatManager
)
from ollama_chat.web_tools import WEB_TOOLS

from .util import create_test_files


# Helper pool manager request side effect recording each call's payload. The payloads are copied
# because the chat messages list is mutated in place as tool call results are appended.
def record_requests(responses, requests):
    def request(*args, **kwargs):
        requests.append((args, copy.deepcopy(kwargs.get('json'))))
        return responses.pop(0)
    return request


# Helper to build a base64-encoded docx attachment
def docx_data(*paragraphs):
    buffer = io.BytesIO()
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    document.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


class TestChatManager(unittest.TestCase):

    def test_chat_fn(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Hi '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'there!'}}).encode('utf-8')
            ]

            # Create a mock show response
            mock_show_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response2.status = 200
            mock_show_response2.json.return_value = {'capabilities': []}

            # Create a second mock chat response
            mock_chat_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response2.status = 200
            mock_chat_response2.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Bye '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'bye!'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [
                mock_show_response, mock_chat_response, mock_show_response2, mock_chat_response2
            ]

            # Create the ChatManager instance
            chat_prompts = ['Hello', 'Goodbye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat calls
            self.assertEqual(mock_pool_manager_instance.request.call_count, 4)
            self.assertListEqual(
                mock_pool_manager_instance.request.call_args_list,
                [
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [
                                {'role': 'user', 'content': 'Hello', 'images': None}
                            ],
                            'stream': True,
                            'think': False
                        },
                        preload_content=False,
                        retries=0
                    ),
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [
                                {'role': 'user', 'content': 'Hello', 'images': None},
                                {'role': 'assistant', 'content': 'Hi there!'},
                                {'role': 'user', 'content': 'Goodbye', 'images': None}
                            ],
                            'stream': True,
                            'think': False
                        },
                        preload_content=False,
                        retries=0
                    )
                ]
            )
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()
            mock_show_response2.close.assert_called_once_with()
            mock_chat_response2.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': 'Hi there!'
                            },
                            {
                                'user': 'Goodbye',
                                'model': 'Bye bye!'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_files(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Hi there!'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create the ChatManager instance with a text and an image attachment
            chat_files = [
                {'name': 'notes.txt', 'type': 'text/plain', 'data': 'the notes'},
                {'name': 'pic.png', 'type': 'image/png', 'data': 'aW1n'}
            ]
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'], files=chat_files)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat call - the file text and image are attached to the user message
            self.assertEqual(mock_pool_manager_instance.request.call_count, 2)
            self.assertListEqual(
                mock_pool_manager_instance.request.call_args_list,
                [
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [
                                {'role': 'user', 'content': 'Hello\n\nthe notes', 'images': ['aW1n']}
                            ],
                            'stream': True,
                            'think': False
                        },
                        preload_content=False,
                        retries=0
                    )
                ]
            )

            # Verify the app config - the attachments are remembered on the exchange
            with app.config() as config:
                self.assertDictEqual(config, {
                    'conversations': [
                        {
                            'id': 'conv1',
                            'model': 'llm',
                            'title': 'Conversation 1',
                            'exchanges': [
                                {
                                    'user': 'Hello',
                                    'model': 'Hi there!',
                                    'files': [
                                        {'name': 'notes.txt', 'type': 'text/plain'},
                                        {'name': 'pic.png', 'type': 'image/png'}
                                    ]
                                }
                            ]
                        }
                    ]
                })

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                config_file = json.load(config_fh)
            self.assertListEqual(
                config_file['conversations'][0]['exchanges'][0]['files'],
                [{'name': 'notes.txt', 'type': 'text/plain'}, {'name': 'pic.png', 'type': 'image/png'}]
            )

    def test_chat_fn_files_attachments(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        bad_docx = base64.b64encode(b'not a docx').decode('utf-8')
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Hi there!'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create the ChatManager instance with images, a readable docx, and a broken docx
            chat_files = [
                {'name': 'pic1.png', 'type': 'image/png', 'data': 'aW1n'},
                {'name': 'pic2.jpg', 'type': 'image/jpeg', 'data': 'aW5n'},
                {'name': 'doc.docx', 'type': 'application/docx', 'data': docx_data('docx notes')},
                {'name': 'bad.docx', 'data': bad_docx}
            ]
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'], files=chat_files)
            app.chats['conv1'] = chat_manager

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Both images are attached and the file text is appended to the user message
            messages = mock_pool_manager_instance.request.call_args_list[1].kwargs['json']['messages']
            self.assertEqual(len(messages), 1)
            self.assertEqual(messages[0]['role'], 'user')
            self.assertListEqual(messages[0]['images'], ['aW1n', 'aW5n'])
            self.assertTrue(
                messages[0]['content'].startswith('Hello\n\ndocx notes\n\n**Error reading bad.docx:** '),
                messages[0]['content']
            )

            # The attachments are remembered on the exchange
            with app.config() as config:
                exchange = config['conversations'][0]['exchanges'][0]
                self.assertListEqual(exchange['files'], [
                    {'name': 'pic1.png', 'type': 'image/png'},
                    {'name': 'pic2.jpg', 'type': 'image/jpeg'},
                    {'name': 'doc.docx', 'type': 'application/docx'},
                    {'name': 'bad.docx'}
                ])

    def test_chat_fn_files_do_template(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ],
                'templates': [
                    {'id': 'tmpl1', 'title': 'Template', 'name': 'tmpl', 'prompts': ['Template prompt']}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Done.'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # The /do command leaves no user message to attach the files to
            chat_files = [
                {'name': 'notes.txt', 'type': 'text/plain', 'data': 'the notes'},
                {'name': 'pic.png', 'type': 'image/png', 'data': 'aW1n'},
                {'name': 'bad.docx', 'data': base64.b64encode(b'not a docx').decode('utf-8')}
            ]
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['/do tmpl'], files=chat_files)
            app.chats['conv1'] = chat_manager

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # The template prompt is the only message sent to the model
            messages = mock_pool_manager_instance.request.call_args_list[1].kwargs['json']['messages']
            self.assertListEqual(messages, [{'role': 'user', 'content': 'Template prompt', 'images': None}])

            # Verify the app config
            with app.config() as config:
                self.assertDictEqual(config, {
                    'conversations': [
                        {
                            'id': 'conv1',
                            'model': 'llm',
                            'title': 'Conversation 1',
                            'exchanges': [
                                {
                                    'user': '/do tmpl',
                                    'model': 'Executing template "tmpl"',
                                    'files': [
                                        {'name': 'notes.txt', 'type': 'text/plain'},
                                        {'name': 'pic.png', 'type': 'image/png'},
                                        {'name': 'bad.docx'}
                                    ]
                                },
                                {'user': 'Template prompt', 'model': 'Done.'}
                            ]
                        }
                    ],
                    'templates': [
                        {'id': 'tmpl1', 'title': 'Template', 'name': 'tmpl', 'prompts': ['Template prompt']}
                    ]
                })


    def test_chat_fn_thinking(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['thinking']}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'thinking': 'Hmmm '}}).encode('utf-8'),
                json.dumps({'message': {'thinking': 'Haw'}}).encode('utf-8'),
                json.dumps({'message': {'content': 'Hi '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'there!'}}).encode('utf-8')
            ]

            # Create a second mock show response
            mock_show_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response2.status = 200
            mock_show_response2.json.return_value = {'capabilities': ['thinking']}

            # Create a second mock chat response
            mock_chat_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response2.status = 200
            mock_chat_response2.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Bye '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'bye!'}}).encode('utf-8')
            ]

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [
                mock_show_response, mock_chat_response, mock_show_response2, mock_chat_response2
            ]

            # Create the ChatManager instance
            chat_prompts = ['Hello', 'Goodbye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat calls
            self.assertListEqual(
                mock_pool_manager_instance.request.call_args_list,
                [
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [
                                {'role': 'user', 'content': 'Hello', 'images': None}
                            ],
                            'stream': True,
                            'think': True
                        },
                        preload_content=False,
                        retries=0
                    ),
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [
                                {'role': 'user', 'content': 'Hello', 'images': None},
                                {'role': 'assistant', 'content': 'Hi there!'},
                                {'role': 'user', 'content': 'Goodbye', 'images': None}
                            ],
                            'stream': True,
                            'think': True
                        },
                        preload_content=False,
                        retries=0
                    )
                ]
            )
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()
            mock_show_response2.close.assert_called_once_with()
            mock_chat_response2.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': 'Hi there!',
                                'thinking': 'Hmmm Haw'
                            },
                            {
                                'user': 'Goodbye',
                                'model': 'Bye bye!'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_cloud_chunking(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['thinking']}

            # A cloud-proxied stream packs multiple newline-delimited JSON objects into a single
            # HTTP chunk and may split an object across chunks. Build the NDJSON stream, then
            # re-split it at byte boundaries that do not align with the JSON object lines.
            ndjson = ''.join(
                json.dumps(obj) + '\n' for obj in [
                    {'message': {'thinking': 'The user '}},
                    {'message': {'thinking': 'said hello'}},
                    {'message': {'content': 'Hi '}},
                    {'message': {'content': 'there!'}}
                ]
            ).encode('utf-8')
            split = ndjson.index(b'there')

            # Create a mock chat response with cloud-style chunk boundaries
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [ndjson[:split], ndjson[split:]]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create and run the ChatManager
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'])
            app.chats['conv1'] = chat_manager
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})
            mock_chat_response.close.assert_called_once_with()

            # Verify the full streamed response was reassembled from the misaligned chunks
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': 'Hi there!',
                                'thinking': 'The user said hello'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)


    def test_chat_fn_truncated_stream(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # A complete object followed by a truncated object (the stream ended mid-object)
            truncated = b'{"message": {"content": "the'
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Hi '}}).encode('utf-8') + b'\n',
                truncated
            ]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create and run the ChatManager
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'])
            app.chats['conv1'] = chat_manager
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})
            mock_chat_response.close.assert_called_once_with()

            # Verify the partial content was kept and the truncation surfaced as an error
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': f'Hi \n**ERROR:** Invalid streamed response: {truncated.decode("utf-8")!r}'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)


    def test_chat_fn_error_show(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 500

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.return_value = mock_show_response

            # Create the ChatManager instance
            chat_prompts = ['Hello', 'Goodbye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat calls
            self.assertEqual(mock_pool_manager_instance.request.call_count, 1)
            self.assertListEqual(
                mock_pool_manager_instance.request.call_args_list,
                [
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0)
                ]
            )
            mock_show_response.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': '\n**ERROR:** Unknown model "llm" (500)'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_error_chat(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['thinking']}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 500

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create the ChatManager instance
            chat_prompts = ['Hello', 'Goodbye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat calls
            self.assertEqual(mock_pool_manager_instance.request.call_count, 2)
            self.assertListEqual(
                mock_pool_manager_instance.request.call_args_list,
                [
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [{'role': 'user', 'content': 'Hello', 'images': None}],
                            'stream': True,
                            'think': True
                        },
                        preload_content=False,
                        retries=0
                    )
                ]
            )
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': '\n**ERROR:** Unknown model "llm" (500)'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_error_chat_chunk(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['thinking']}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'error': 'BOOM!'}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create the ChatManager instance
            chat_prompts = ['Hello', 'Goodbye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat calls
            self.assertEqual(mock_pool_manager_instance.request.call_count, 2)
            self.assertListEqual(
                mock_pool_manager_instance.request.call_args_list,
                [
                    unittest.mock.call('POST', 'http://127.0.0.1:11434/api/show', json={'model': 'llm'}, retries=0),
                    unittest.mock.call(
                        'POST',
                        'http://127.0.0.1:11434/api/chat',
                        json={
                            'model': 'llm',
                            'messages': [{'role': 'user', 'content': 'Hello', 'images': None}],
                            'stream': True,
                            'think': True
                        },
                        preload_content=False,
                        retries=0
                    )
                ]
            )
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': '\n**ERROR:** BOOM!'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_stop(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Hi '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'there!'}}).encode('utf-8')
            ]

            # Create a second mock show response
            mock_show_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response2.status = 200
            mock_show_response2.json.return_value = {'capabilities': []}

            # Create a seconde mock chat response
            mock_chat_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response2.status = 200
            mock_chat_response2.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Bye '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'bye!'}}).encode('utf-8')
            ]

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [
                mock_show_response, mock_chat_response, mock_show_response2, mock_chat_response2
            ]

            # Create the ChatManager instance
            chat_prompts = ['Hello', 'Goodbye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            chat_manager.stop = True
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()
            mock_show_response2.close.assert_not_called()
            mock_chat_response2.close.assert_not_called()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': 'Hello','model': ''}]}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_help(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value

            # Create the ChatManager instance
            chat_prompts = ['/?']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            mock_pool_manager_instance.request.assert_not_called()
            self.assertDictEqual(app.chats, {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': [{'user': '/?'}]}
                ]
            }
            with app.config() as config:
                exchange = config['conversations'][0]['exchanges'][0]
                self.assertTrue(exchange['model'].startswith('```\nusage: /{?,dir,do,file,image,url}'))
                del exchange['model']
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                config = json.load(config_fh)
                exchange = config['conversations'][0]['exchanges'][0]
                self.assertTrue(exchange['model'].startswith('```\nusage: /{?,dir,do,file,image,url}'))
                del exchange['model']
                self.assertEqual(config, expected_config)


    def test_chat_fn_show(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            })),
            ('test.txt', 'file content')
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value

            # Create the ChatManager instance
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            chat_prompts = [f'This file:\n\n/file {temp_posix}/test.txt -n']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            mock_pool_manager_instance.request.assert_not_called()
            self.assertDictEqual(app.chats, {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': f'''\
This file:

/file {temp_posix}/test.txt -n''',
                                'model': f'''\
This file:

<{_escape_markdown_text(temp_posix)}/test.txt>
```
file content
```
</ {_escape_markdown_text(temp_posix)}/test.txt>'''
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_do(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ],
                'templates': [
                    {'id': 'tmpl1', 'name': 'bye', 'title': 'Goodbye', 'prompts': ['Goodbye']}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Bye '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'bye!'}}).encode('utf-8')
            ]

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create the ChatManager instance
            chat_prompts = ['/do bye']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {'user': '/do bye', 'model': 'Executing template "bye"'},
                            {'user': 'Goodbye', 'model': 'Bye bye!'}
                        ]
                    }
                ],
                'templates': [
                    {'id': 'tmpl1', 'name': 'bye', 'title': 'Goodbye', 'prompts': ['Goodbye']}
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_do_variables(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ],
                'templates': [
                    {
                        'id': 'tmpl1',
                        'name': 'bye',
                        'title': 'Goodbye',
                        'variables': [{'name': 'name', 'label': 'Name'}],
                        'prompts': ['Goodbye, {{name}}']
                    }
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': []}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Bye '}}).encode('utf-8'),
                json.dumps({'message': {'content': 'bye!'}}).encode('utf-8')
            ]

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = [mock_show_response, mock_chat_response]

            # Create the ChatManager instance
            chat_prompts = ['/do bye -v name Joe']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})
            mock_show_response.close.assert_called_once_with()
            mock_chat_response.close.assert_called_once_with()

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {'user': '/do bye -v name Joe', 'model': 'Executing template "bye" - name = "Joe"'},
                            {'user': 'Goodbye, Joe', 'model': 'Bye bye!'}
                        ]
                    }
                ],
                'templates': [
                    {
                        'id': 'tmpl1',
                        'name': 'bye',
                        'title': 'Goodbye',
                        'variables': [{'name': 'name', 'label': 'Name'}],
                        'prompts': ['Goodbye, {{name}}']
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)


    def test_chat_fn_do_unknown_template(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Configure the mock session instance
            mock_pool_manager_instance = mock_pool_manager.return_value

            # Create the ChatManager instance
            chat_prompts = ['/do unknown']
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', chat_prompts)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))
            mock_thread.return_value.start.assert_called_once_with()
            self.assertTrue(mock_thread.return_value.daemon)

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            mock_pool_manager_instance.request.assert_not_called()
            self.assertDictEqual(app.chats, {})

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': '/do unknown',
                                'model': '\n**ERROR:** unknown template "unknown"'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)

    def test_chat_fn_web_search(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        tool_call = {'function': {'name': 'web_search', 'arguments': {'query': 'python news'}}}
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread') as mock_thread, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager, \
             unittest.mock.patch(
                 'ollama_chat.chat.web_search',
                 return_value=[{'title': 'Title', 'url': 'http://example.com/', 'snippet': 'Snippet'}]
             ) as mock_web_search:

            # Create a mock show response with the tools capability
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['tools']}

            # Create a mock chat response with a tool call
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Looking... '}}).encode('utf-8'),
                json.dumps({'message': {'tool_calls': [tool_call]}}).encode('utf-8')
            ]

            # Create a mock chat response with the final answer
            mock_chat_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response2.status = 200
            mock_chat_response2.read_chunked.return_value = [
                json.dumps({'message': {'content': 'The answer.'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            requests = []
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = record_requests(
                [mock_show_response, mock_chat_response, mock_chat_response2], requests
            )

            # Create the ChatManager instance
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'], search=True)
            app.chats['conv1'] = chat_manager
            mock_thread.assert_called_once_with(target=ChatManager.chat_thread_fn, args=(chat_manager,))

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the ollama.chat calls - the model's tools and the tool result messages
            mock_web_search.assert_called_once_with('python news', max_results=5)
            self.assertEqual(mock_pool_manager_instance.request.call_count, 3)
            chat_calls = [payload for args, payload in requests if args[1].endswith('/api/chat')]
            self.assertEqual(len(chat_calls), 2)
            self.assertIn('tools', chat_calls[0])
            self.assertListEqual(chat_calls[0]['tools'], WEB_TOOLS)
            self.assertListEqual(
                chat_calls[0]['messages'],
                [
                    {'role': 'user', 'content': 'Hello', 'images': None}
                ]
            )
            self.assertIn('tools', chat_calls[1])
            self.assertListEqual(
                chat_calls[1]['messages'],
                [
                    {'role': 'user', 'content': 'Hello', 'images': None},
                    {'role': 'assistant', 'content': 'Looking... ', 'tool_calls': [tool_call]},
                    {
                        'role': 'tool',
                        'tool_name': 'web_search',
                        'content': 'Search results for "python news":\n\n1. Title\nhttp://example.com/\nSnippet'
                    }
                ]
            )

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': 'Looking... The answer.',
                                'tools': [{'action': 'search', 'value': 'python news'}]
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

            # Verify the config file
            with open(config_path, 'r', encoding='utf-8') as config_fh:
                self.assertEqual(json.load(config_fh), expected_config)

    def test_chat_fn_web_search_unsupported_model(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:

            # Create a mock show response without the tools capability
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['completion']}

            # Create a mock chat response
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'The answer.'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            requests = []
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = record_requests(
                [mock_show_response, mock_chat_response], requests
            )

            # Create the ChatManager instance
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'], search=True)
            app.chats['conv1'] = chat_manager

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the chat request doesn't offer the tools
            chat_calls = [payload for args, payload in requests if args[1].endswith('/api/chat')]
            self.assertEqual(len(chat_calls), 1)
            self.assertNotIn('tools', chat_calls[0])

            # Verify the app config
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': '\n**Web search is unavailable:** this model does not support ' \
                                    'tool calling.The answer.'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

    def test_chat_fn_web_search_tool_error(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        tool_call = {'function': {'name': 'fetch_page', 'arguments': {'url': 'file:///etc/passwd'}}}
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager, \
             unittest.mock.patch(
                 'ollama_chat.chat.fetch_page', side_effect=ValueError('only http and https URLs are allowed')
             ):

            # Create a mock show response with the tools capability
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['tools']}

            # Create a mock chat response with a tool call
            mock_chat_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response.status = 200
            mock_chat_response.read_chunked.return_value = [
                json.dumps({'message': {'tool_calls': [tool_call]}}).encode('utf-8')
            ]

            # Create a mock chat response with the final answer
            mock_chat_response2 = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_chat_response2.status = 200
            mock_chat_response2.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Cannot read that page.'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            requests = []
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = record_requests(
                [mock_show_response, mock_chat_response, mock_chat_response2], requests
            )

            # Create the ChatManager instance
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'], search=True)
            app.chats['conv1'] = chat_manager

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify the tool error is returned to the model as text
            chat_calls = [payload for args, payload in requests if args[1].endswith('/api/chat')]
            self.assertEqual(len(chat_calls), 2)
            self.assertListEqual(
                chat_calls[1]['messages'],
                [
                    {'role': 'user', 'content': 'Hello', 'images': None},
                    {'role': 'assistant', 'content': '', 'tool_calls': [tool_call]},
                    {
                        'role': 'tool',
                        'tool_name': 'fetch_page',
                        'content': 'Error: only http and https URLs are allowed'
                    }
                ]
            )

            # Verify the app config - no tool usage is recorded for a failed tool
            expected_config = {
                'conversations': [
                    {
                        'id': 'conv1',
                        'model': 'llm',
                        'title': 'Conversation 1',
                        'exchanges': [
                            {
                                'user': 'Hello',
                                'model': 'Cannot read that page.'
                            }
                        ]
                    }
                ]
            }
            with app.config() as config:
                self.assertDictEqual(config, expected_config)

    def test_chat_fn_web_search_limit(self):
        test_files = [
            ('ollama-chat.json', json.dumps({
                'conversations': [
                    {'id': 'conv1', 'model': 'llm', 'title': 'Conversation 1', 'exchanges': []}
                ]
            }))
        ]
        tool_call = {'function': {'name': 'web_search', 'arguments': {'query': 'news'}}}
        with create_test_files(test_files) as temp_dir, \
             unittest.mock.patch('threading.Thread'), \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager, \
             unittest.mock.patch(
                 'ollama_chat.chat.web_search',
                 return_value=[{'title': 'Title', 'url': 'http://example.com/', 'snippet': 'Snippet'}]
             ):

            # Create a mock show response with the tools capability
            mock_show_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_show_response.status = 200
            mock_show_response.json.return_value = {'capabilities': ['tools']}

            # Every chat response asks for another tool call
            mock_tool_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_tool_response.status = 200
            mock_tool_response.read_chunked.return_value = [
                json.dumps({'message': {'tool_calls': [tool_call]}}).encode('utf-8')
            ]
            mock_final_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
            mock_final_response.status = 200
            mock_final_response.read_chunked.return_value = [
                json.dumps({'message': {'content': 'Done.'}}).encode('utf-8')
            ]

            # Configure the mock pool manager instance
            requests = []
            mock_pool_manager_instance = mock_pool_manager.return_value
            mock_pool_manager_instance.request.side_effect = record_requests(
                [mock_show_response, *[mock_tool_response for _ in range(5)], mock_final_response], requests
            )

            # Create the ChatManager instance
            config_path = os.path.join(temp_dir, 'ollama-chat.json')
            app = OllamaChat(config_path)
            chat_manager = ChatManager(app, 'conv1', ['Hello'], search=True)
            app.chats['conv1'] = chat_manager

            # Run the thread function
            ChatManager.chat_thread_fn(chat_manager)
            self.assertDictEqual(app.chats, {})

            # Verify at most 5 tool call rounds - the last request has no tools
            chat_calls = [payload for args, payload in requests if args[1].endswith('/api/chat')]
            self.assertEqual(len(chat_calls), 6)
            self.assertEqual(sum(1 for payload in chat_calls if 'tools' in payload), 5)

            # Verify the app config
            with app.config() as config:
                exchange = config['conversations'][0]['exchanges'][0]
                self.assertEqual(exchange['model'], 'Done.')
                self.assertListEqual(exchange['tools'], [{'action': 'search', 'value': 'news'}] * 5)


class TestConfigTemplatePrompts(unittest.TestCase):

    def test_basic(self):
        template = {
            'title': 'Simple Template',
            'prompts': ['Hello world', 'Second prompt']
        }
        variable_values = {}
        title, prompts = config_template_prompts(template, variable_values)
        self.assertEqual(title, 'Simple Template')
        self.assertListEqual(prompts, ['Hello world', 'Second prompt'])


    def test_variables(self):
        template = {
            'title': 'Hello {{name}}',
            'prompts': ['Greetings {{name}}', 'How are you {{name}}?'],
            'variables': [{'name': 'name'}]
        }
        variable_values = {'name': 'Alice'}
        title, prompts = config_template_prompts(template, variable_values)
        self.assertEqual(title, 'Hello Alice')
        self.assertListEqual(prompts, ['Greetings Alice', 'How are you Alice?'])


    def test_missing_variable(self):
        template = {
            'title': 'Hello {{name}}',
            'prompts': ['Greetings {{name}}'],
            'variables': [{'name': 'name'}]
        }
        variable_values = {}
        with self.assertRaises(ValueError) as context:
            config_template_prompts(template, variable_values)
        self.assertEqual(str(context.exception), 'missing variable value for "name"')


    def test_unknown_variable(self):
        template = {
            'title': 'Hello {{name}}',
            'prompts': ['Greetings {{name}}'],
            'variables': [{'name': 'name'}]
        }
        variable_values = {'name': 'Alice', 'age': '30'}
        with self.assertRaises(ValueError) as context:
            config_template_prompts(template, variable_values)
        self.assertEqual(str(context.exception), 'unknown variable "age"')


    def test_multiple_variables(self):
        template = {
            'title': '{{greeting}} {{name}}',
            'prompts': ['{{greeting}} dear {{name}}', '{{name}}, how are you?'],
            'variables': [{'name': 'greeting'}, {'name': 'name'}]
        }
        variable_values = {'greeting': 'Hello', 'name': 'Bob'}
        title, prompts = config_template_prompts(template, variable_values)
        self.assertEqual(title, 'Hello Bob')
        self.assertListEqual(prompts, ['Hello dear Bob', 'Bob, how are you?'])


class TestProcessCommands(unittest.TestCase):

    def test_no_commands(self):
        flags = {}
        self.assertEqual(_process_commands(None, 'Hello, how are you?', flags), 'Hello, how are you?')
        self.assertDictEqual(flags, {})


    def test_help_top(self):
        flags = {}
        self.assertEqual(_process_commands(None, '/?', flags), 'Displaying top-level help')
        self.assertTrue(flags['help'].startswith('usage: /{?,dir,do,file,image,url}'))


    def test_help(self):
        flags = {}
        self.assertEqual(_process_commands(None, '/file test.txt -h', flags), 'Displaying help for "file" command')
        self.assertTrue(flags['help'].startswith('usage: /file [-h] [-n] file'))


    def test_dir(self):
        test_files = [
            ('test.txt', 'Test 1'),
            (('subdir', 'test2.txt'), 'Test 2'),
            (('subdir', 'test3.md'), '# Test 3')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(None, f'/dir {temp_posix} .txt', flags),
                f'''\
<{_escape_markdown_text(temp_posix)}/test.txt>
Test 1
</ {_escape_markdown_text(temp_posix)}/test.txt>'''
            )
            self.assertDictEqual(flags, {})


    def test_dir_depth(self):
        test_files = [
            ('test.txt', 'Test 1'),
            (('subdir', 'test2.txt'), 'Test 2'),
            (('subdir', 'test3.md'), '# Test 3')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(None, f'/dir {temp_posix} .txt -d 2', flags),
                f'''\
<{_escape_markdown_text(temp_posix)}/subdir/test2.txt>
Test 2
</ {_escape_markdown_text(temp_posix)}/subdir/test2.txt>

<{_escape_markdown_text(temp_posix)}/test.txt>
Test 1
</ {_escape_markdown_text(temp_posix)}/test.txt>'''
            )
            self.assertDictEqual(flags, {})


    def test_dir_exclude(self):
        test_files = [
            ('test.txt', 'Test 1'),
            (('subdir', 'test2.txt'), 'Test 2'),
            (('subdir2', 'test3.txt'), 'Test 3')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(None, f'/dir {temp_posix} .txt -d 2 -x test.txt -x subdir2/', flags),
                f'''\
<{_escape_markdown_text(temp_posix)}/subdir/test2.txt>
Test 2
</ {_escape_markdown_text(temp_posix)}/subdir/test2.txt>'''
            )
            self.assertDictEqual(flags, {})


    def test_dir_no_files(self):
        with create_test_files([]) as temp_dir, \
             self.assertRaises(ValueError) as cm_exc:
            temp_posix = pathlib.Path(temp_dir).as_posix()
            _process_commands(None, f'/dir {temp_posix} .txt', {})
        self.assertEqual(str(cm_exc.exception), f'no files found in directory "{temp_posix}"')


    def test_do(self):
        flags = {}
        self.assertEqual(_process_commands(None, '/do template_name -v var1 val1', flags), 'Executing template "template_name"')
        self.assertDictEqual(flags, {'do': [('template_name', {'var1': 'val1'})]})


    def test_do_multiple(self):
        flags = {}
        self.assertEqual(
            _process_commands(
                None,
                '''\
/do template_name -v var1 val1

/do template_name -v var1 val2
''',
                flags
            ),
            '''\
Executing template "template_name"

Executing template "template_name"
'''
        )
        self.assertDictEqual(flags, {
            'do': [
                ('template_name', {'var1': 'val1'}),
                ('template_name', {'var1': 'val2'})
            ]
        })


    def test_file(self):
        test_files = [
            ('test.txt', 'file content')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(None, f'/file {temp_posix}/test.txt', flags),
                f'''\
<{_escape_markdown_text(temp_posix)}/test.txt>
file content
</ {_escape_markdown_text(temp_posix)}/test.txt>'''
            )
            self.assertDictEqual(flags, {})


    def test_file_show(self):
        test_files = [
            ('test.txt', 'file content')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(None, f'/file {temp_posix}/test.txt -n', flags),
                f'''\
<{_escape_markdown_text(temp_posix)}/test.txt>
```
file content
```
</ {_escape_markdown_text(temp_posix)}/test.txt>'''
            )
            self.assertDictEqual(flags, {'show': True})


    def test_file_show2(self):
        test_files = [
            ('test.txt', 'file content'),
            ('test2.txt', 'file content 2')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(
                    None,
                    f'''\
/file {temp_posix}/test.txt

/file {temp_posix}/test2.txt -n
''',
                    flags
                ),
                f'''\
<{_escape_markdown_text(temp_posix)}/test.txt>
```
file content
```
</ {_escape_markdown_text(temp_posix)}/test.txt>

<{_escape_markdown_text(temp_posix)}/test2.txt>
```
file content 2
```
</ {_escape_markdown_text(temp_posix)}/test2.txt>
'''
            )
            self.assertDictEqual(flags, {'show': True})


    def test_image(self):
        test_files = [
            ('test.jpg', 'image data')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(_process_commands(None, f'/image {temp_posix}/test.jpg', flags), '')
            self.assertDictEqual(flags, {'images': [base64.b64encode(b'image data').decode('utf-8')]})


    def test_image_multiple(self):
        test_files = [
            ('test.jpg', 'image data'),
            ('test2.jpg', 'image data 2')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(
                    None,
                    f'''\
/image {temp_posix}/test.jpg

/image {temp_posix}/test2.jpg
''',
                    flags
                ),
                '\n\n\n'
            )
            self.assertDictEqual(flags, {
                'images': [
                    base64.b64encode(b'image data').decode('utf-8'),
                    base64.b64encode(b'image data 2').decode('utf-8')
                ]
            })


    def test_url(self):
        mock_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        mock_response.status = 200
        mock_response.data = b'url content'

        mock_chat = unittest.mock.Mock()
        mock_chat.app.pool_manager.request.return_value = mock_response

        flags = {}
        self.assertEqual(
            _process_commands(mock_chat, '/url http://example.com', flags),
            '''\
<http://example.com>
url content
</ http://example.com>'''
        )
        self.assertDictEqual(flags, {})


    def test_url_error(self):
        mock_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        mock_response.status = 500
        mock_response.data = b'error content'

        mock_chat = unittest.mock.Mock()
        mock_chat.app.pool_manager.request.return_value = mock_response

        flags = {}
        with self.assertRaises(urllib3.exceptions.HTTPError) as cm_exc:
            _process_commands(mock_chat, '/url http://example.com', flags)
        self.assertEqual(str(cm_exc.exception), 'Failed to load URL "http://example.com"')
        self.assertDictEqual(flags, {})


    def test_url_show(self):
        mock_response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        mock_response.status = 200
        mock_response.data = b'url content'

        mock_chat = unittest.mock.Mock()
        mock_chat.app.pool_manager.request.return_value = mock_response

        flags = {}
        self.assertEqual(
            _process_commands(mock_chat, '/url http://example.com -n', flags),
            '''\
<http://example.com>
```
url content
```
</ http://example.com>'''
        )
        self.assertDictEqual(flags, {'show': True})

        # Show mode requires a second render pass, but the URL is still fetched only once
        self.assertEqual(mock_chat.app.pool_manager.request.call_count, 1)
        mock_response.close.assert_called_once_with()


    def test_multiple_commands(self):
        test_files = [
            ('test.txt', 'file content')
        ]
        with create_test_files(test_files) as temp_dir:
            temp_posix = str(pathlib.Path(temp_dir).as_posix())
            flags = {}
            self.assertEqual(
                _process_commands(None, f'Hello\n\n/?\n\n/file {temp_posix}/test.txt', flags),
                f'''\
Hello

Displaying top-level help

<{_escape_markdown_text(temp_posix)}/test.txt>
file content
</ {_escape_markdown_text(temp_posix)}/test.txt>'''
            )
            self.assertIn('help', flags)


    def test_file_error(self):
        with create_test_files([]) as temp_dir:
            flags = {}
            with self.assertRaises(FileNotFoundError):
                _process_commands(None, f'/file {temp_dir}/nonexistent.txt', flags)


class TestWebToolCallHelpers(unittest.TestCase):

    def test_tool_call_arguments_dict(self):
        tool_name, arguments = _tool_call_arguments(
            {'function': {'name': 'web_search', 'arguments': {'query': 'python news'}}}
        )
        self.assertEqual(tool_name, 'web_search')
        self.assertDictEqual(arguments, {'query': 'python news'})

    def test_tool_call_arguments_json_string(self):
        tool_name, arguments = _tool_call_arguments(
            {'function': {'name': 'web_search', 'arguments': '{"query": "python news"}'}}
        )
        self.assertEqual(tool_name, 'web_search')
        self.assertDictEqual(arguments, {'query': 'python news'})

    def test_tool_call_arguments_invalid_json(self):
        tool_name, arguments = _tool_call_arguments(
            {'function': {'name': 'web_search', 'arguments': '{query: python news'}}
        )
        self.assertEqual(tool_name, 'web_search')
        self.assertDictEqual(arguments, {})

    def test_tool_call_arguments_not_a_dict(self):
        tool_name, arguments = _tool_call_arguments(
            {'function': {'name': 'web_search', 'arguments': ['python news']}}
        )
        self.assertEqual(tool_name, 'web_search')
        self.assertDictEqual(arguments, {})

    def test_tool_call_arguments_missing(self):
        self.assertTupleEqual(_tool_call_arguments({}), ('', {}))
        self.assertTupleEqual(_tool_call_arguments({'function': {}}), ('', {}))

    def test_run_tool_unknown(self):
        with self.assertRaises(ValueError) as raises:
            _run_tool(None, 'bogus_tool', {})
        self.assertEqual(str(raises.exception), 'unknown tool "bogus_tool"')

    def test_run_tool_search_missing_query(self):
        for arguments in ({}, {'query': '   '}):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError) as raises:
                _run_tool(None, 'web_search', arguments)
            self.assertEqual(str(raises.exception), 'missing "query" argument')

    def test_run_tool_search_max_results(self):
        with unittest.mock.patch(
            'ollama_chat.chat.web_search', return_value=[{'title': 'T', 'url': 'http://e.com/', 'snippet': 'S'}]
        ) as mock_web_search:
            _, event = _run_tool(None, 'web_search', {'query': 'q', 'max_results': 2})
            mock_web_search.assert_called_once_with('q', max_results=2)
            self.assertDictEqual(event, {'action': 'search', 'value': 'q'})

    def test_run_tool_search_no_results(self):
        with unittest.mock.patch('ollama_chat.chat.web_search', return_value=[]) as mock_web_search:
            text, event = _run_tool(None, 'web_search', {'query': 'nothing here'})
        mock_web_search.assert_called_once_with('nothing here', max_results=5)
        self.assertEqual(text, 'No results found for "nothing here"')
        self.assertDictEqual(event, {'action': 'search', 'value': 'nothing here'})

    def test_run_tool_fetch_page_missing_url(self):
        with self.assertRaises(ValueError) as raises:
            _run_tool(None, 'fetch_page', {})
        self.assertEqual(str(raises.exception), 'missing "url" argument')

    def test_run_tool_fetch_page(self):
        chat = unittest.mock.Mock()
        with unittest.mock.patch('ollama_chat.chat.fetch_page', return_value='Page text') as mock_fetch_page:
            self.assertTupleEqual(
                _run_tool(chat, 'fetch_page', {'url': 'https://example.com/'}),
                ('Page text', {'action': 'open', 'value': 'https://example.com/'})
            )
        mock_fetch_page.assert_called_once_with('https://example.com/', chat.app.pool_manager)
