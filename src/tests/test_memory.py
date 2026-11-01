# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import datetime
import os
import unittest
import unittest.mock

from ollama_chat.memory import (
    daily_file_path, ensure_workspace, find_memory_lines, forget, memory_context, memory_file_path,
    read_memory_file, remember, workspace_dir
)

from .util import create_test_files


class TestMemory(unittest.TestCase):

    def test_workspace_dir_default(self):
        with unittest.mock.patch.dict(os.environ):
            os.environ.pop('OLLAMA_CHAT_WORKSPACE', None)
            self.assertEqual( \
                str(workspace_dir({})), \
                os.path.expanduser(os.path.join('~', 'ollama-chat-workspace')) \
            )


    def test_workspace_dir_env(self):
        with unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': 'env-workspace'}):
            self.assertEqual(str(workspace_dir({})), 'env-workspace')


    def test_workspace_dir_config(self):
        with unittest.mock.patch.dict(os.environ, {'OLLAMA_CHAT_WORKSPACE': 'env-workspace'}):
            self.assertEqual(str(workspace_dir({'workspace': 'config-workspace'})), 'config-workspace')


    def test_ensure_workspace(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            self.assertTrue(os.path.isfile(os.path.join(temp_dir, 'memory', 'USER.md')))
            self.assertTrue(os.path.isfile(os.path.join(temp_dir, 'memory', 'MEMORY.md')))
            self.assertTrue(os.path.isdir(os.path.join(temp_dir, 'memory', 'daily')))

            # A second call doesn't overwrite existing content
            remember(temp_dir, 'test note')
            ensure_workspace(temp_dir)
            self.assertIn('test note', read_memory_file(temp_dir, 'MEMORY.md'))


    def test_read_memory_file_missing(self):
        with create_test_files([]) as temp_dir:
            self.assertEqual(read_memory_file(temp_dir, 'USER.md'), '')


    def test_memory_file_path(self):
        with create_test_files([]) as temp_dir:
            self.assertEqual( \
                memory_file_path(temp_dir, 'USER.md'), \
                os.path.join(temp_dir, 'memory', 'USER.md') \
            )
            self.assertEqual( \
                memory_file_path(temp_dir, 'MEMORY.md.bak'), \
                os.path.join(temp_dir, 'memory', 'MEMORY.md.bak') \
            )


    def test_memory_file_path_invalid(self):
        self.assertRaises(ValueError, memory_file_path, '.', 'unknown.md')

        # Paths that escape the workspace are rejected
        self.assertRaises(ValueError, memory_file_path, os.getcwd(), os.path.join(os.pardir, 'x.md'))


    def test_daily_file_path(self):
        self.assertEqual( \
            daily_file_path('', datetime.date(2026, 2, 3)), \
            os.path.join('', 'memory', 'daily', '2026-02-03.md') \
        )


    def test_remember(self):
        with create_test_files([]) as temp_dir:
            remember(temp_dir, '  likes tea  ')
            self.assertEqual(read_memory_file(temp_dir, 'MEMORY.md').splitlines()[-1], 'likes tea')
            remember(temp_dir, 'likes coffee')
            self.assertIn('likes tea', read_memory_file(temp_dir, 'MEMORY.md'))
            self.assertIn('likes coffee', read_memory_file(temp_dir, 'MEMORY.md'))


    def test_find_memory_lines(self):
        test_files = [
            (('memory', 'MEMORY.md'), '# Memory\n\nAny case: MAYBE likes tea\nlikes coffee\n')
        ]
        with create_test_files(test_files) as temp_dir:
            self.assertEqual( \
                find_memory_lines(temp_dir, 'TEA'), \
                [(2, 'Any case: MAYBE likes tea')] \
            )
            self.assertEqual(find_memory_lines(temp_dir, 'water'), [])


    def test_forget(self):
        test_files = [
            (('memory', 'MEMORY.md'), '# Memory\n\nAny case: MAYBE likes tea\nlikes coffee\n')
        ]
        with create_test_files(test_files) as temp_dir:
            deleted = forget(temp_dir, 'TEA')
            self.assertEqual(deleted, 1)
            content = read_memory_file(temp_dir, 'MEMORY.md')
            self.assertNotIn('tea', content)
            self.assertIn('likes coffee', content)

            # The backup contains the original content
            backup = read_memory_file(temp_dir, 'MEMORY.md.bak')
            self.assertIn('Any case: MAYBE likes tea', backup)

            # Forgetting everything leaves the header
            forget(temp_dir, 'likes coffee')
            self.assertEqual(read_memory_file(temp_dir, 'MEMORY.md'), '# Memory\n\n')


    def test_memory_context_empty(self):
        with create_test_files([]) as temp_dir:
            self.assertIsNone(memory_context(temp_dir, 'Hello'))


    def test_memory_context_limit(self):
        # A non-positive limit returns None
        with unittest.mock.patch('ollama_chat.memory.read_memory_file', return_value='something'):
            self.assertIsNone(memory_context('.', 'Hello', limit=0))
            self.assertIsNone(memory_context('.', 'Hello', limit=-1))


    def test_memory_context(self):
        test_files = [
            (('memory', 'USER.md'), 'The user likes tea.'),
            (('memory', 'MEMORY.md'), '# Memory\n\nAny case: MAYBE likes tea\nlikes coffee\n')
        ]
        with create_test_files(test_files) as temp_dir:
            context = memory_context(temp_dir, 'Why me?')
            self.assertIn('The user likes tea.', context)
            self.assertIn('# Memory', context)
            self.assertIn('Any case: MAYBE likes tea', context)
            self.assertIn('likes coffee', context)


    def test_memory_context_relevant(self):
        # Memory relevant to the request is preferred when over the limit
        lines = [f'mark{ix} ' + 'q' * 380 for ix in range(1, 12)]
        lines.insert(5, 'zebras ' + 'q' * 380)
        test_files = [
            (('memory', 'MEMORY.md'), '\n'.join(lines) + '\n')
        ]
        with create_test_files(test_files) as temp_dir:
            context = memory_context(temp_dir, 'tell me about zebras')
            self.assertIn('zebras', context)
            self.assertNotIn('mark11', context)


    def test_memory_context_fallback(self):
        # Without relevant lines, the most recent lines are used
        lines = [f'mark{ix} ' + 'z' * 380 for ix in range(1, 12)]
        test_files = [
            (('memory', 'MEMORY.md'), '\n'.join(lines) + '\n')
        ]
        with create_test_files(test_files) as temp_dir:
            context = memory_context(temp_dir, 'something completely different', limit=1000)
            self.assertIn('mark11', context)
            self.assertIn('mark10', context)
            self.assertNotIn('mark2 ', context)
