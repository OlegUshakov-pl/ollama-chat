# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import datetime
import json
import os
import unittest
import unittest.mock

import urllib3

from ollama_chat.memory import (
    MAX_MEMORY_FACTS, USER_FACT_KEYS, add_memory_proposals, apply_memory_proposal, daily_file_path,
    ensure_workspace, filter_memory_facts, find_memory_lines, forget, log_memory_error,
    memory_context, memory_cursor, memory_extraction_model, memory_extraction_message,
    memory_fact_line, memory_file_path, memory_settings, normalize_memory_text, pending_path,
    pop_memory_proposal, propose_memory, read_memory_file, read_pending, remember,
    restore_memory_proposal, sanitize_memory_fact, set_memory_cursor, time_context, update_pending,
    user_timezone, workspace_dir, write_memory_file
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


    def test_write_memory_file(self):
        with create_test_files([]) as temp_dir:
            write_memory_file(temp_dir, 'USER.md', '# About the user\n\n- Name: Oleg\n')
            self.assertEqual(read_memory_file(temp_dir, 'USER.md'), '# About the user\n\n- Name: Oleg\n')
            self.assertRaises(ValueError, write_memory_file, temp_dir, 'unknown.md', '')


    def test_user_timezone(self):
        test_files = [
            (('memory', 'USER.md'), '# About the user\n\n- Name: Oleg\n- Timezone: Europe/Warsaw\n')
        ]
        with create_test_files(test_files) as temp_dir:
            timezone = user_timezone(temp_dir)
            self.assertIsNotNone(timezone)
            self.assertEqual(str(timezone), 'Europe/Warsaw')


    def test_user_timezone_case(self):
        # The "- Timezone:" bullet key matches case-insensitively
        test_files = [
            (('memory', 'USER.md'), '# About the user\n\n- TIMEZONE: Europe/Warsaw\n- Name: Oleg\n')
        ]
        with create_test_files(test_files) as temp_dir:
            self.assertEqual(str(user_timezone(temp_dir)), 'Europe/Warsaw')


    def test_user_timezone_none(self):
        with create_test_files([]) as temp_dir:
            self.assertIsNone(user_timezone(temp_dir))

        # An unparseable zone name falls back to None
        test_files = [
            (('memory', 'USER.md'), '- Timezone: Not/AZone\n')
        ]
        with create_test_files(test_files) as temp_dir:
            self.assertIsNone(user_timezone(temp_dir))


    def test_time_context_none(self):
        # No memory directory - no time context
        with create_test_files([]) as temp_dir:
            self.assertIsNone(time_context(temp_dir))


    def test_time_context(self):
        test_files = [
            (('memory', 'USER.md'), '- Timezone: Europe/Warsaw\n')
        ]
        with create_test_files(test_files) as temp_dir:
            context = time_context(temp_dir)
            self.assertRegex(context, r'^Current date and time: [A-Z][a-z]{2}, \d{4}-\d{2}-\d{2} \d{2}:\d{2} \(Europe/Warsaw\)$')


    def test_time_context_local(self):
        # Without a USER.md zone the local time zone (UTC offset) is used
        test_files = [
            (('memory', 'USER.md'), '- Name: Oleg\n')
        ]
        with create_test_files(test_files) as temp_dir:
            context = time_context(temp_dir)
            self.assertRegex(context, r'^Current date and time: [A-Z][a-z]{2}, \d{4}-\d{2}-\d{2} \d{2}:\d{2} \(UTC[+-]\d{4}\)$')


class TestAutoMemory(unittest.TestCase):

    def test_memory_settings_defaults(self):
        self.assertDictEqual(memory_settings(None), {
            'enabled': False, 'model': '', 'every': 3, 'minChars': 40, 'maxPending': 30
        })
        self.assertDictEqual(memory_settings({
            'autoMemory': True, 'memoryModel': 'gemma4:e4b', 'memoryEvery': 0,
            'memoryMinChars': -5, 'memoryMaxPending': 0
        }), {
            'enabled': True, 'model': 'gemma4:e4b', 'every': 1, 'minChars': 0, 'maxPending': 1
        })


    def test_memory_extraction_model(self):
        # No memoryModel - only a local Ollama conversation's model may be used
        self.assertEqual(memory_extraction_model({}, None, 'llm'), 'llm')
        self.assertEqual(memory_extraction_model({}, 'ollama', 'llm'), 'llm')

        # A cloud provider without memoryModel must never receive the memory
        cloud_config = {'providers': [{'id': 'openai', 'name': 'OpenAI', 'type': 'openai'}]}
        self.assertIsNone(memory_extraction_model(cloud_config, 'openai', 'gpt-4o'))
        self.assertIsNone(memory_extraction_model(cloud_config, 'openai', None))

        # An explicitly configured memoryModel is always a local Ollama model
        self.assertEqual( \
            memory_extraction_model({'memoryModel': 'gemma4:e4b'}, 'openai', 'gpt-4o'), \
            'gemma4:e4b' \
        )


    def test_pending_store(self):
        with create_test_files([]) as temp_dir:
            self.assertEqual(read_pending(temp_dir), {'cursors': {}, 'proposals': []})
            self.assertEqual(pending_path(temp_dir), os.path.join(temp_dir, 'memory', 'pending.json'))

            # The update runs under the lock and writes atomically
            self.assertEqual(update_pending(temp_dir, lambda pending: pending['cursors'].update({'conv1': 2})), None)
            self.assertEqual(read_pending(temp_dir)['cursors'], {'conv1': 2})

            # No .md proposal file reaches the system prompt
            self.assertFalse(os.path.exists(os.path.join(temp_dir, 'memory', 'pending.md')))


    def test_normalize_memory_text(self):
        self.assertEqual(normalize_memory_text('- 2026-11-25: Likes  TEA!'), 'likes tea')
        self.assertEqual(normalize_memory_text('City: Warsaw'), 'city warsaw')


    def test_memory_extraction_message(self):
        message = memory_extraction_message(['first', 'second'], 'memory line', '- City: Warsaw')
        self.assertIn('1. first', message)
        self.assertIn('2. second', message)
        self.assertIn('memory line', message)
        self.assertIn('City: Warsaw', message)

        # The context blocks are trimmed to a reasonable size
        message = memory_extraction_message(['hello'], 'm' * 10000, 'u' * 10000)
        self.assertLessEqual(len(message), 6000 + 200)


    def test_propose_memory(self):
        response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        response.status = 200
        # Ollama returns the schema-constrained JSON as a string in message.content
        response.json.return_value = {'message': {'content': json.dumps({'facts': [
            {'action': 'add', 'target': 'memory', 'text': 'Работает над ollama-chat'}
        ]})}}
        with unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            mock_pool_manager.return_value.request.return_value = response
            facts = propose_memory(['Работает над ollama-chat'], '', '', 'gemma4:e4b', base_url='http://ollama:11434')

        self.assertEqual(facts, [{'action': 'add', 'target': 'memory', 'text': 'Работает над ollama-chat'}])
        args, kwargs = mock_pool_manager.return_value.request.call_args
        self.assertEqual(args, ('POST', 'http://ollama:11434/api/chat'))
        payload = kwargs['json']
        self.assertFalse(payload['stream'])
        self.assertFalse(payload['think'])
        self.assertEqual(payload['options'], {'temperature': 0})
        self.assertEqual(payload['model'], 'gemma4:e4b')
        self.assertEqual(payload['format']['required'], ['facts'])
        self.assertEqual(len(payload['messages']), 2)
        self.assertEqual(payload['messages'][0]['role'], 'system')
        self.assertIn('1. Работает над ollama-chat', payload['messages'][1]['content'])
        response.close.assert_called_once_with()


    def test_propose_memory_bad_json(self):
        response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        response.status = 200
        response.json.side_effect = ValueError('not json')
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            mock_pool_manager.return_value.request.return_value = response
            self.assertEqual(propose_memory(['some durable fact text'], '', '', 'llm', workspace=temp_dir), [])

            logs = os.listdir(os.path.join(temp_dir, 'logs'))
            self.assertEqual(len(logs), 1)
            with open(os.path.join(temp_dir, 'logs', logs[0]), 'r', encoding='utf-8') as log_fh:
                self.assertIn('memory error:', log_fh.read())


    def test_propose_memory_bad_content_json(self):
        response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        response.status = 200
        response.json.return_value = {'message': {'content': 'not json at all'}}
        with create_test_files([]) as temp_dir, \
             unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            mock_pool_manager.return_value.request.return_value = response
            self.assertEqual(propose_memory(['some durable fact text'], '', '', 'llm', workspace=temp_dir), [])
            with open(os.path.join(temp_dir, 'logs', os.listdir(os.path.join(temp_dir, 'logs'))[0]), \
                      'r', encoding='utf-8') as log_fh:
                self.assertIn('invalid extraction JSON', log_fh.read())


    def test_propose_memory_fenced_json(self):
        response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        response.status = 200
        response.json.return_value = {'message': {
            'content': '```json\n{"facts": [{"action": "add", "target": "memory", "text": "likes tea"}]}\n```'
        }}
        with unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            mock_pool_manager.return_value.request.return_value = response
            self.assertEqual( \
                propose_memory(['likes tea'], '', '', 'llm'), \
                [{'action': 'add', 'target': 'memory', 'text': 'likes tea'}] \
            )


    def test_propose_memory_http_error(self):
        response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
        response.status = 500
        with unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            mock_pool_manager.return_value.request.return_value = response
            self.assertEqual(propose_memory(['some durable fact text'], '', '', 'llm'), [])
        response.close.assert_called_once_with()


    def test_propose_memory_no_messages_or_model(self):
        with unittest.mock.patch('urllib3.PoolManager') as mock_pool_manager:
            self.assertEqual(propose_memory([], '', '', 'llm'), [])
            self.assertEqual(propose_memory(['hello'], '', '', ''), [])
        mock_pool_manager.assert_not_called()


    def test_filter_add_duplicate(self):
        memory_text = '# Memory\n\n- 2026-11-25: likes coffee\n'
        facts = [
            {'action': 'add', 'target': 'memory', 'text': 'Likes coffee'},
            {'action': 'add', 'target': 'memory', 'text': 'Likes tea'}
        ]
        self.assertEqual(filter_memory_facts(facts, memory_text, ''), [
            {'action': 'add', 'target': 'memory', 'text': 'Likes tea'}
        ])


    def test_filter_update_delete(self):
        memory_text = '# Memory\n\n- 2026-11-25: City: Warsaw\n- 2026-11-25: likes coffee\n'
        user_text = '# About the user\n\n- City: Warsaw\n'
        facts = [
            {
                'action': 'update', 'target': 'user', 'text': 'City: Rzeszów',
                'replaces': 'City: Warsaw'
            },
            {
                'action': 'delete', 'target': 'memory', 'text': 'likes coffee',
                'replaces': '2026-11-25: likes coffee'
            }
        ]
        filtered = filter_memory_facts(facts, memory_text, user_text)
        self.assertEqual(filtered, [
            {
                'action': 'update', 'target': 'user', 'text': 'City: Rzeszów',
                'replaces': 'City: Warsaw', 'matched': '- City: Warsaw'
            },
            {
                'action': 'delete', 'target': 'memory', 'text': 'likes coffee',
                'replaces': '2026-11-25: likes coffee', 'matched': '- 2026-11-25: likes coffee'
            }
        ])


    def test_filter_unmatched_update_becomes_add(self):
        memory_text = '- likes coffee\n'
        facts = [
            {'action': 'update', 'target': 'memory', 'text': 'likes tea', 'replaces': 'unknown line'},
            {'action': 'delete', 'target': 'memory', 'text': 'unknown', 'replaces': 'unknown line'}
        ]
        self.assertEqual(filter_memory_facts(facts, memory_text, ''), [
            {'action': 'add', 'target': 'memory', 'text': 'likes tea'}
        ])


    def test_filter_secrets_and_markup(self):
        # Leading markup is stripped so a fact can't break the memory file's structure
        self.assertEqual(sanitize_memory_fact('# - likes tea', 'memory'), 'likes tea')
        self.assertEqual(sanitize_memory_fact('  > likes\ntea  ', 'memory'), 'likes tea')
        self.assertEqual(len(sanitize_memory_fact('word ' * 60, 'memory')), 200)
        self.assertIsNone(sanitize_memory_fact('my password is hunter2', 'memory'))
        self.assertIsNone(sanitize_memory_fact('api_key: abc123', 'memory'))
        self.assertIsNone(sanitize_memory_fact('token = abcdefghijklmnopqrstuvwxyz', 'memory'))
        self.assertIsNone(sanitize_memory_fact('card 4111 1111 1111 1111', 'memory'))
        self.assertIsNone(sanitize_memory_fact('key: abcdefghijklmnopqrstuvwxyz12345', 'memory'))
        self.assertIsNone(sanitize_memory_fact('PESEL 12345678901', 'memory'))

        # User facts require one of the allowed keys, normalized to its canonical spelling
        self.assertEqual(sanitize_memory_fact('city: Rzeszów', 'user'), 'City: Rzeszów')
        self.assertIn('Reply language', USER_FACT_KEYS)
        self.assertIsNone(sanitize_memory_fact('Hometown: Rzeszów', 'user'))
        self.assertIsNone(sanitize_memory_fact('just some text', 'user'))


    def test_filter_invalid_facts(self):
        facts = [
            {'action': 'invent', 'target': 'memory', 'text': 'likes tea'},
            {'action': 'add', 'target': 'tool', 'text': 'likes tea'},
            'not a dict',
            {'action': 'add', 'target': 'memory'}
        ]
        self.assertEqual(filter_memory_facts(facts, '', ''), [])


    def test_filter_max_facts(self):
        facts = [{'action': 'add', 'target': 'memory', 'text': f'fact number {index}'} for index in range(10)]
        self.assertEqual(len(filter_memory_facts(facts, '', '')), MAX_MEMORY_FACTS)


    def test_log_memory_error_bad_workspace(self):
        # Even a bad workspace must not raise
        log_memory_error(None, 'something failed')


    def test_memory_fact_line(self):
        now = datetime.datetime(2026, 11, 25, 14, 3, tzinfo=datetime.timezone.utc)
        self.assertEqual(memory_fact_line('likes tea', now=now), '- 2026-11-25: likes tea')


    def test_apply_memory_add(self):
        test_files = [(('memory', 'MEMORY.md'), '# Memory\n\n')]
        with create_test_files(test_files) as temp_dir:
            content = apply_memory_proposal( \
                temp_dir, {'action': 'add', 'target': 'memory', 'text': 'likes tea'}, \
                now=datetime.datetime(2026, 11, 25, tzinfo=datetime.timezone.utc) \
            )
            self.assertIn('- 2026-11-25: likes tea', content)
            self.assertEqual(read_memory_file(temp_dir, 'MEMORY.md'), content)
            self.assertIn('# Memory', read_memory_file(temp_dir, 'MEMORY.md.bak'))
            self.assertNotIn('likes tea', read_memory_file(temp_dir, 'MEMORY.md.bak'))


    def test_apply_memory_update_delete(self):
        test_files = [(('memory', 'MEMORY.md'), '# Memory\n\n- 2026-11-25: City: Warsaw\n- likes coffee\n')]
        with create_test_files(test_files) as temp_dir:
            apply_memory_proposal( \
                temp_dir, \
                { \
                    'action': 'update', 'target': 'memory', 'text': 'City: Rzeszów', \
                    'matched': '- 2026-11-25: City: Warsaw' \
                }, \
                now=datetime.datetime(2026, 11, 25, tzinfo=datetime.timezone.utc) \
            )
            content = read_memory_file(temp_dir, 'MEMORY.md')
            self.assertIn('- 2026-11-25: City: Rzeszów', content)
            self.assertNotIn('Warsaw', content)
            self.assertIn('City: Warsaw', read_memory_file(temp_dir, 'MEMORY.md.bak'))

            apply_memory_proposal( \
                temp_dir, \
                {'action': 'delete', 'target': 'memory', 'text': 'likes coffee', 'matched': '- likes coffee'} \
            )
            self.assertNotIn('coffee', read_memory_file(temp_dir, 'MEMORY.md'))


    def test_apply_memory_bad_text(self):
        with create_test_files([]) as temp_dir:
            self.assertRaises( \
                ValueError, apply_memory_proposal, temp_dir, \
                {'action': 'add', 'target': 'memory', 'text': 'my password is hunter2'} \
            )
            self.assertRaises( \
                ValueError, apply_memory_proposal, temp_dir, \
                {'action': 'update', 'target': 'memory', 'text': 'likes tea', 'matched': 'missing line'} \
            )
            self.assertRaises( \
                ValueError, apply_memory_proposal, temp_dir, \
                {'action': 'add', 'target': 'unknown', 'text': 'likes tea'} \
            )


    def test_apply_user_fact(self):
        test_files = [(('memory', 'USER.md'), '# About the user\n\n- Name: Oleg\n- City: Warsaw\n')]
        with create_test_files(test_files) as temp_dir:
            # add updates an existing key
            apply_memory_proposal(temp_dir, {'action': 'add', 'target': 'user', 'text': 'City: Rzeszów'})
            content = read_memory_file(temp_dir, 'USER.md')
            self.assertIn('- City: Rzeszów', content)
            self.assertNotIn('Warsaw', content)

            # update changes exactly the matched line
            apply_memory_proposal( \
                temp_dir, \
                {'action': 'update', 'target': 'user', 'text': 'Name: Oleg U.', 'matched': '- Name: Oleg'} \
            )
            self.assertIn('- Name: Oleg U.', read_memory_file(temp_dir, 'USER.md'))

            # delete removes the matched line
            apply_memory_proposal( \
                temp_dir, \
                {'action': 'delete', 'target': 'user', 'text': 'City: Rzeszów', 'matched': '- City: Rzeszów'} \
            )
            self.assertNotIn('Rzeszów', read_memory_file(temp_dir, 'USER.md'))
            self.assertIn('- City: Rzeszów', read_memory_file(temp_dir, 'USER.md.bak'))


    def test_apply_user_fact_profile_limit(self):
        test_files = [(('memory', 'USER.md'), '# About the user\n\n- Name: Oleg\n')]
        with create_test_files(test_files) as temp_dir:
            fact = {'action': 'add', 'target': 'user', 'text': 'Other: ' + 'word ' * 30}
            self.assertRaises(ValueError, apply_memory_proposal, temp_dir, fact, profile_limit=50)
            self.assertEqual(read_memory_file(temp_dir, 'USER.md'), test_files[0][1])


    def test_add_and_pop_proposals(self):
        now = datetime.datetime(2026, 11, 25, 14, 3, 11, tzinfo=datetime.timezone.utc)
        facts = [
            {'action': 'add', 'target': 'memory', 'text': 'likes tea'},
            {'action': 'add', 'target': 'user', 'text': 'City: Rzeszów'}
        ]
        with create_test_files([]) as temp_dir:
            added = add_memory_proposals(temp_dir, facts, conversation_id='conv1', created_at=now)
            self.assertEqual(len(added), 2)
            self.assertEqual(added[0]['id'], 'p-20261125-0001')
            self.assertEqual(added[1]['id'], 'p-20261125-0002')
            self.assertEqual(added[0]['conversationId'], 'conv1')
            self.assertEqual(added[0]['createdAt'], '2026-11-25T14:03:11+00:00')

            # The queue limit is enforced
            self.assertEqual(add_memory_proposals(temp_dir, facts, max_pending=2, created_at=now), [])

            # Cursors and pop/restore work under the lock
            set_memory_cursor(temp_dir, 'conv1', 7)
            self.assertEqual(memory_cursor(temp_dir, 'conv1'), 7)
            self.assertEqual(memory_cursor(temp_dir, 'conv2'), 0)
            self.assertEqual(pop_memory_proposal(temp_dir, added[0]['id']), added[0])
            self.assertIsNone(pop_memory_proposal(temp_dir, added[0]['id']))
            restore_memory_proposal(temp_dir, added[0])
            self.assertEqual(len(read_pending(temp_dir)['proposals']), 2)
