# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

from contextlib import contextmanager
import datetime
import json
import os
import threading
import unittest
import unittest.mock

from ollama_chat.memory import ensure_workspace
from ollama_chat.tasks import (
    _run_task, task_log_text, task_upsert,
    load_tasks, log_task_error, log_task_event, parse_task_days, parse_task_time, run_stored_task,
    run_task_once,
    save_tasks, task_add, task_days_text, task_id_new, task_last_slot, task_remove, tasks_summary,
    tasks_path, write_task_result, TaskManager
)

from .util import create_test_files


# A task manager app proxy for unit tests
class TestApp():
    __slots__ = ('config_dict', 'pool_manager')


    def __init__(self, config_dict=None, pool_manager=None):
        self.config_dict = config_dict if config_dict is not None else {'conversations': []}
        self.pool_manager = pool_manager if pool_manager is not None else unittest.mock.sentinel.pool


    @contextmanager
    def config(self, save=False):
        yield self.config_dict


TEST_TASK = {
    'id': 'briefing',
    'name': 'Briefing',
    'time': '09:00',
    'days': [1, 2, 3, 4, 5, 6, 7],
    'prompt': 'Make a report',
    'model': 'llm',
    'num_ctx': None,
    'tools': ['web_search', 'fetch_page', 'check_email'],
    'dest': 'daily',
    'lastRun': None,
    'lastError': None
}


# Create a task manager without starting the scheduler thread (for tick tests)
def make_task_manager(app):
    with unittest.mock.patch('threading.Thread'):
        return TaskManager(app)


class TestTaskFiles(unittest.TestCase):

    def test_tasks_path(self):
        self.assertEqual(str(tasks_path('ws')), os.path.join('ws', 'tasks.json'))


    def test_load_save_tasks(self):
        with create_test_files([]) as temp_dir:
            self.assertEqual(load_tasks(temp_dir), [])
            save_tasks(temp_dir, [TEST_TASK])
            self.assertListEqual(load_tasks(temp_dir), [TEST_TASK])


    def test_load_tasks_invalid(self):
        with create_test_files([('tasks.json', 'not json')]) as temp_dir:
            self.assertEqual(load_tasks(temp_dir), [])
        with create_test_files([('tasks.json', json.dumps({'tasks': []}))]) as temp_dir:
            self.assertEqual(load_tasks(temp_dir), [])


class TestTaskIdNew(unittest.TestCase):

    def test_task_id_new(self):
        tasks = [{'id': 'briefing'}]
        self.assertEqual(task_id_new('Briefing!', []), 'briefing')
        self.assertEqual(task_id_new('Daily Briefing', tasks), 'daily-briefing')
        self.assertEqual(task_id_new('Briefing', tasks), 'briefing-1')
        self.assertEqual(task_id_new('!!!', []), 'task')


    def test_task_id_new_multiple_suffixes(self):
        tasks = [{'id': 'briefing'}, {'id': 'briefing-1'}]
        self.assertEqual(task_id_new('Briefing', tasks), 'briefing-2')


class TestParseTaskTime(unittest.TestCase):

    def test_parse_task_time(self):
        self.assertEqual(parse_task_time('09:00'), datetime.time(9, 0))
        self.assertEqual(parse_task_time('23:59'), datetime.time(23, 59))
        self.assertEqual(parse_task_time(' 7:05 '), datetime.time(7, 5))


    def test_parse_task_time_invalid(self):
        for text in ['', '9', '9:5', '24:00', '12:60', 'abc', '09:00:00']:
            with self.subTest(text=text):
                self.assertRaises(ValueError, parse_task_time, text)


class TestParseTaskDays(unittest.TestCase):

    def test_parse_task_days_presets(self):
        self.assertListEqual(parse_task_days('all'), [1, 2, 3, 4, 5, 6, 7])
        self.assertListEqual(parse_task_days('WEEKDAYS'), [1, 2, 3, 4, 5])
        self.assertListEqual(parse_task_days('weekends'), [6, 7])


    def test_parse_task_days_list(self):
        self.assertListEqual(parse_task_days('1,3,5'), [1, 3, 5])
        self.assertListEqual(parse_task_days('7'), [7])


    def test_parse_task_days_invalid(self):
        for text in ['', '0', '8', 'none', '1,,2']:
            with self.subTest(text=text):
                self.assertRaises(ValueError, parse_task_days, text)


class TestTaskDaysText(unittest.TestCase):

    def test_task_days_text(self):
        self.assertEqual(task_days_text([1, 2, 3, 4, 5, 6, 7]), 'every day')
        self.assertEqual(task_days_text([1]), 'Mon')
        self.assertEqual(task_days_text([1, 3, 5]), 'Mon, Wed, Fri')
        self.assertEqual(task_days_text([]), 'never')


class TestTasksSummary(unittest.TestCase):

    def test_tasks_summary_empty(self):
        self.assertEqual(tasks_summary([]), 'There are no scheduled tasks.')


    def test_tasks_summary(self):
        task = dict(TEST_TASK, lastRun='2026-02-03 09:00', lastError=None)
        summary = tasks_summary([task])
        self.assertIn('1. briefing - "Briefing" - 09:00 every day - model llm', summary)
        self.assertIn('last run 2026-02-03 09:00', summary)


    def test_tasks_summary_error(self):
        task = dict(TEST_TASK, lastError='Boom')
        summary = tasks_summary([task])
        self.assertIn('ERROR: Boom', summary)


class TestTaskAddRemove(unittest.TestCase):

    def test_task_add(self):
        with create_test_files([]) as temp_dir:
            task_id = task_add( \
                temp_dir, 'Briefing', parse_task_time('09:00'), [1, 3], 'prompt text', 'llm' \
            )
            self.assertEqual(task_id, 'briefing')
            tasks = load_tasks(temp_dir)
            self.assertListEqual( \
                tasks,
                [{
                    'id': 'briefing',
                    'name': 'Briefing',
                    'time': '09:00',
                    'days': [1, 3],
                    'prompt': 'prompt text',
                    'model': 'llm',
                    'num_ctx': None,
                    'tools': ['web_search', 'fetch_page', 'check_email'],
                    'dest': 'daily',
                    'enabled': True,
                    'lastRun': None,
                    'lastError': None
                }]
            )

            # A second task gets a unique ID
            task_id2 = task_add(temp_dir, 'Briefing', parse_task_time('1:30'), parse_task_days('all'), 'p2', 'llm2')
            self.assertEqual(task_id2, 'briefing-1')
            self.assertListEqual(load_tasks(temp_dir)[1]['days'], [1, 2, 3, 4, 5, 6, 7])


    def test_task_add_tools_and_ctx(self):
        with create_test_files([]) as temp_dir:
            task_add( \
                temp_dir, 'T', parse_task_time('09:00'), parse_task_days('all'), 'p', 'llm', \
                num_ctx=8192, tools='web_search' \
            )
            tasks = load_tasks(temp_dir)
            self.assertEqual(tasks[0]['num_ctx'], 8192)
            self.assertListEqual(tasks[0]['tools'], ['web_search'])

            # Email sending is an opt-in tool, off by default
            task_add(temp_dir, 'T2', parse_task_time('09:00'), parse_task_days('all'), 'p', 'llm', tools='check_email')
            self.assertListEqual(load_tasks(temp_dir)[1]['tools'], ['check_email'])
            task_add(temp_dir, 'T3', parse_task_time('09:00'), parse_task_days('all'), 'p', 'llm', tools='send_email')
            self.assertListEqual(load_tasks(temp_dir)[2]['tools'], ['send_email'])


    def test_task_add_unknown_tool(self):
        with create_test_files([]) as temp_dir:
            with self.assertRaises(ValueError) as caught:
                task_add(temp_dir, 'T', parse_task_time('09:00'), parse_task_days('all'), 'p', 'llm', tools='write_file')
            self.assertIn('write_file', str(caught.exception))
            self.assertEqual(load_tasks(temp_dir), [])


    def test_task_remove(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            task_remove(temp_dir, 'briefing')
            self.assertEqual(load_tasks(temp_dir), [])
            with self.assertRaises(ValueError):
                task_remove(temp_dir, 'briefing')


class TestTaskLastSlot(unittest.TestCase):

    TASK = dict(TEST_TASK, time='09:00', days=[1, 2, 3, 4, 5, 6, 7])


    def test_same_day(self):
        now = datetime.datetime(2026, 2, 3, 10, 20)  # Tuesday
        self.assertEqual( \
            task_last_slot(self.TASK, now), \
            datetime.datetime(2026, 2, 3, 9, 0) \
        )


    def test_previous_day(self):
        task = dict(self.TASK, time='09:00')
        now = datetime.datetime(2026, 2, 3, 8, 0)  # Tuesday, before the run time
        self.assertEqual(task_last_slot(task, now), datetime.datetime(2026, 2, 2, 9, 0))


    def test_previous_week(self):
        # Now is Sunday; the task runs on Mondays only
        task = dict(self.TASK, time='09:00', days=[1])
        now = datetime.datetime(2026, 2, 8, 23, 0)
        self.assertEqual(task_last_slot(task, now), datetime.datetime(2026, 2, 2, 9, 0))


    def test_no_days(self):
        task = dict(self.TASK, days=[])
        now = datetime.datetime(2026, 2, 3, 10, 0)
        self.assertIsNone(task_last_slot(task, now))


    def test_invalid_time(self):
        task = dict(self.TASK, time='not-a-time')
        self.assertRaises(ValueError, task_last_slot, task, datetime.datetime(2026, 2, 3, 10, 0))


class TestTaskResult(unittest.TestCase):

    def test_write_task_result(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            now = datetime.datetime(2026, 2, 3, 9, 30)
            write_task_result(temp_dir, TEST_TASK, now, 'The report.\n')
            write_task_result(temp_dir, TEST_TASK, now, 'Another report.')
            with open( \
                os.path.join(temp_dir, 'memory', 'daily', '2026-02-03.md'), encoding='utf-8' \
            ) as daily_fh:
                contents = daily_fh.read()
            self.assertIn('## Briefing (09:30)\n', contents)
            self.assertIn('The report.', contents)
            self.assertIn('Another report.', contents)


    def test_log_task_error(self):
        with create_test_files([]) as temp_dir:
            now = datetime.datetime(2026, 2, 3, 9, 30, 15)
            log_task_error(temp_dir, 'briefing', ValueError('boom'), now=now)
            with open(os.path.join(temp_dir, 'logs', '2026-02-03.log'), encoding='utf-8') as log_fh:
                contents = log_fh.read()
            self.assertEqual(contents, '09:30:15 ERROR task "briefing": boom\n')


    def test_log_task_event(self):
        with create_test_files([]) as temp_dir:
            now = datetime.datetime(2026, 2, 3, 9, 30, 15)
            log_task_event(temp_dir, 'briefing', 'report saved', now=now)
            with open(os.path.join(temp_dir, 'logs', '2026-02-03.log'), encoding='utf-8') as log_fh:
                contents = log_fh.read()
            self.assertEqual(contents, '09:30:15 OK task "briefing": report saved\n')


# A context manager combining the ollama_chat and ollama_show mocks. "rounds" is a list of
# round-specific chunk lists - round N of the tool-calling loop returns round N's chunks.
@contextmanager
def mock_ollama(rounds, capabilities=None):
    with unittest.mock.patch('ollama_chat.tasks.ollama_chat', side_effect=[iter(r) for r in rounds]) as mock_chat:
        with unittest.mock.patch('ollama_chat.tasks.ollama_show', \
            return_value=None if capabilities is None else {'capabilities': capabilities} \
        ) as mock_show:
            yield mock_chat, mock_show


class TestRunStoredTask(unittest.TestCase):

    def test_run_stored_task_success(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            now = datetime.datetime(2026, 2, 3, 9, 30)
            with mock_ollama([[{'message': {'content': 'The report.'}}]], capabilities=['tools']):
                report = run_stored_task(temp_dir, unittest.mock.sentinel.pool, 'briefing', now=now)
            self.assertEqual(report, 'The report.')
            tasks = load_tasks(temp_dir)
            self.assertEqual(tasks[0]['lastRun'], '2026-02-03 09:30')
            self.assertIsNone(tasks[0]['lastError'])
            self.assertTrue( \
                os.path.isfile(os.path.join(temp_dir, 'memory', 'daily', '2026-02-03.md')) \
            )
            with open(os.path.join(temp_dir, 'logs', '2026-02-03.log'), encoding='utf-8') as log_fh:
                self.assertIn('OK task "briefing"', log_fh.read())


    def test_run_stored_task_failure(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            broken_task = dict(TEST_TASK, model=None)
            save_tasks(temp_dir, [broken_task])
            now = datetime.datetime(2026, 2, 3, 9, 30)
            report = run_stored_task(temp_dir, unittest.mock.sentinel.pool, 'briefing', now=now)
            self.assertIsNone(report)
            tasks = load_tasks(temp_dir)
            self.assertEqual(tasks[0]['lastRun'], '2026-02-03 09:30')
            self.assertIn('no model', tasks[0]['lastError'])
            with open(os.path.join(temp_dir, 'logs', '2026-02-03.log'), encoding='utf-8') as log_fh:
                self.assertIn('ERROR task "briefing"', log_fh.read())


    def test_run_stored_task_missing(self):
        with create_test_files([]) as temp_dir:
            self.assertRaises(ValueError, run_stored_task, temp_dir, None, 'no-such-task')


    def test_run_stored_task_empty_report(self):
        # An empty model response is a failure - lastError is set and nothing is written to daily
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            now = datetime.datetime(2026, 2, 3, 9, 30)
            with mock_ollama([[{'message': {'content': '  \n'}}]], capabilities=['tools']):
                report = run_stored_task(temp_dir, unittest.mock.sentinel.pool, 'briefing', now=now)
            self.assertIsNone(report)
            tasks = load_tasks(temp_dir)
            self.assertIn('empty report', tasks[0]['lastError'])
            self.assertFalse(os.path.isfile(os.path.join(temp_dir, 'memory', 'daily', '2026-02-03.md')))
            with open(os.path.join(temp_dir, 'logs', '2026-02-03.log'), encoding='utf-8') as log_fh:
                self.assertIn('empty report', log_fh.read())


    def test_run_stored_task_stopped(self):
        # A set stop event aborts the run - lastError reports the stop and nothing is written
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            now = datetime.datetime(2026, 2, 3, 9, 30)
            stop = threading.Event()
            stop.set()
            with mock_ollama([[{'message': {'content': 'The report.'}}]], capabilities=['tools']):
                report = run_stored_task( \
                    temp_dir, unittest.mock.sentinel.pool, 'briefing', now=now, stop=stop \
                )
            self.assertIsNone(report)
            tasks = load_tasks(temp_dir)
            self.assertIn('stopped', tasks[0]['lastError'])
            self.assertFalse(os.path.isfile(os.path.join(temp_dir, 'memory', 'daily', '2026-02-03.md')))


    def test_stop_task_not_running(self):
        with create_test_files([]) as temp_dir:
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            self.assertFalse(make_task_manager(app).stop_task('briefing'))


    def test_stop_task_running(self):
        # While a task runs (tracked), stop_task sets its stop event and returns True; the
        # tracking entry is cleared after the run
        with create_test_files([]) as temp_dir:
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            observed = []
            def run_fn(stop_event):
                running_before = task_manager.task_running('briefing')
                stop_result = task_manager.stop_task('briefing')
                observed.append((running_before, stop_result, stop_event.is_set()))
                return 'done'
            self.assertEqual(task_manager._run_tracked('briefing', run_fn), 'done')
            self.assertListEqual(observed, [(True, True, True)])
            self.assertFalse(task_manager.task_running('briefing'))
            self.assertFalse(task_manager.stop_task('briefing'))


    def test_run_task_once_never_raises(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            broken_task = dict(TEST_TASK, model=None)
            self.assertIsNone(run_task_once(unittest.mock.sentinel.pool, temp_dir, broken_task))
            self.assertTrue(os.path.isdir(os.path.join(temp_dir, 'logs')))


class TestRunTask(unittest.TestCase):

    def test_run_task_simple(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK, tools=[])
            with mock_ollama([[{'message': {'content': 'The report.'}}]]):
                report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
            self.assertEqual(report, 'The report.')


    def test_run_task_tool_rounds(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK)  # tools: web_search, fetch_page
            tool_call = {'function': {'name': 'web_search', 'arguments': {'query': 'q'}}}
            rounds = [
                [{'message': {'content': 'searching', 'tool_calls': [tool_call]}}],
                [{'message': {'content': 'The report after search.'}}]
            ]
            with mock_ollama(rounds, capabilities=['tools']):
                with unittest.mock.patch( \
                    'ollama_chat.chat._run_tool', return_value=('tool result', {'action': 'search', 'value': 'q'}) \
                ):
                    report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
                self.assertEqual(report, 'The report after search.')


    def test_run_task_tool_budget_exhausted(self):
        # When the tool call budget is exhausted, the model is told to write its final answer -
        # and tool calls in the no-tools round are ignored (MiMo emits them even then)
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK)  # tools: web_search, fetch_page
            tool_call = {'function': {'name': 'web_search', 'arguments': {'query': 'q'}}}
            rounds = [
                [{'message': {'content': 'searching', 'tool_calls': [tool_call]}}],
                [{'message': {'tool_calls': [tool_call]}}],  # a phantom tool call, no content
                [{'message': {'content': 'The final report.'}}]
            ]
            with mock_ollama(rounds, capabilities=['tools']) as (mock_chat, _mock_show):
                with unittest.mock.patch('ollama_chat.chat._MAX_TOOL_ROUNDS', 1):
                    with unittest.mock.patch( \
                        'ollama_chat.chat._run_tool', return_value=('tool result', {'action': 'search', 'value': 'q'}) \
                    ):
                        report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
                self.assertEqual(report, 'The final report.')
                final_messages = mock_chat.call_args_list[-1].args[2]
                self.assertEqual(final_messages[-1], {'role': 'user', 'content': unittest.mock.ANY})
                self.assertIn('final answer', final_messages[-1]['content'])


    def test_run_task_tool_rounds_per_task(self):
        # The task's own tool_rounds limit caps the tool-call rounds (default is 5)
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK, tool_rounds=1)  # tools: web_search, fetch_page
            tool_call = {'function': {'name': 'web_search', 'arguments': {'query': 'q'}}}
            rounds = [
                [{'message': {'content': 'searching', 'tool_calls': [tool_call]}}],
                [{'message': {'content': 'The report after one search.'}}]
            ]
            with mock_ollama(rounds, capabilities=['tools']) as (mock_chat, _mock_show):
                with unittest.mock.patch( \
                    'ollama_chat.chat._run_tool', return_value=('tool result', {'action': 'search', 'value': 'q'}) \
                ):
                    report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
            self.assertEqual(report, 'The report after one search.')
            # The second round has no tools - the task's limit is reached
            chat_calls = [call for call in mock_chat.call_args_list if call.kwargs.get('tools') is not None]
            self.assertEqual(len(chat_calls), 1)

    def test_run_task_no_tools_capability(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK)  # tools: web_search, fetch_page, check_email

            # The model can't tool-call, so the tools argument is null
            with mock_ollama([[{'message': {'content': 'The report.'}}]], capabilities=[]) as (mock_chat, _mock_show):
                report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
            self.assertEqual(report, 'The report.')
            self.assertIsNone(mock_chat.call_args.kwargs.get('tools'))


    def test_run_task_send_email_tool_error(self):
        # A model trying to send email from a scheduled task gets an error as text - no draft, no send
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK)  # tools: web_search, fetch_page, check_email
            tool_call = {'function': {'name': 'send_email', 'arguments': {'to': 'x@y.z', 'subject': 's', 'body': 'b'}}}
            rounds = [
                [{'message': {'content': 'sending', 'tool_calls': [tool_call]}}],
                [{'message': {'content': 'The report.'}}]
            ]
            with mock_ollama(rounds, capabilities=['tools']):
                report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
            self.assertEqual(report, 'The report.')
            self.assertNotIn('email', os.listdir(temp_dir))


    def test_run_task_send_email_opt_in(self):
        # A task may send email when its tools list explicitly includes send_email
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK, tools=['send_email'])
            tool_call = {
                'function': {'name': 'send_email', 'arguments': {'to': 'x@y.z', 'subject': 's', 'body': 'b'}}
            }
            rounds = [
                [{'message': {'content': 'sending', 'tool_calls': [tool_call]}}],
                [{'message': {'content': 'The report.'}}]
            ]
            with mock_ollama(rounds, capabilities=['tools']):
                with unittest.mock.patch('ollama_chat.chat.smtp_send_email') as mock_smtp_send:
                    report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
            self.assertEqual(report, 'The report.')
            mock_smtp_send.assert_called_once_with('x@y.z', 's', 'b')


    def test_tick_disabled_task(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [dict(TEST_TASK, enabled=False)])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_not_called()


class TestTaskUpsertAndLog(unittest.TestCase):

    def test_task_upsert_create(self):
        with create_test_files([]) as temp_dir:
            task = task_upsert( \
                temp_dir, None, 'Briefing', parse_task_time('9:15'), [1, 2], 'Make a report', 'llm', \
                num_ctx='4096', tools='web_search, send_email', enabled=True \
            )
            self.assertEqual(task['id'], 'briefing')
            self.assertEqual(task['time'], '09:15')
            self.assertListEqual(task['days'], [1, 2])
            self.assertEqual(task['num_ctx'], 4096)
            self.assertListEqual(task['tools'], ['web_search', 'send_email'])
            self.assertTrue(task['enabled'])
            self.assertIsNone(task['lastRun'])
            saved = load_tasks(temp_dir)[0]
            self.assertEqual(saved['id'], 'briefing')


    def test_task_upsert_tool_rounds(self):
        with create_test_files([]) as temp_dir:
            task = task_upsert( \
                temp_dir, None, 'Briefing', parse_task_time('9:15'), [1], 'Make a report', 'llm', \
                tools='web_search', tool_rounds='10' \
            )
            self.assertEqual(task['tool_rounds'], 10)

            # An out-of-range or non-numeric limit is rejected
            self.assertRaises( \
                ValueError, task_upsert, temp_dir, 'briefing', 'Briefing', parse_task_time('9:15'), \
                [1], 'Make a report', 'llm', tools='web_search', tool_rounds='51' \
            )
            self.assertRaises( \
                ValueError, task_upsert, temp_dir, 'briefing', 'Briefing', parse_task_time('9:15'), \
                [1], 'Make a report', 'llm', tools='web_search', tool_rounds='abc' \
            )
            # An empty limit resets to the default (None)
            task = task_upsert( \
                temp_dir, 'briefing', 'Briefing', parse_task_time('9:15'), [1], 'Make a report', 'llm', \
                tools='web_search', tool_rounds='' \
            )
            self.assertIsNone(task['tool_rounds'])


    def test_task_upsert_update_keeps_last_run(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [dict(TEST_TASK, lastRun='2026-02-03 09:00', lastError=None, enabled=True)])
            task = task_upsert( \
                temp_dir, 'briefing', 'New name', parse_task_time('10:30'), [6, 7], 'New prompt', 'llm2', \
                num_ctx=None, tools='', enabled=False \
            )
            self.assertEqual(task['name'], 'New name')
            self.assertEqual(task['time'], '10:30')
            self.assertListEqual(task['days'], [6, 7])
            self.assertListEqual(task['tools'], ['web_search', 'fetch_page', 'check_email'])
            self.assertFalse(task['enabled'])
            self.assertEqual(task['lastRun'], '2026-02-03 09:00')  # lastRun is kept on update
            self.assertEqual(task['model'], 'llm2')
            self.assertEqual(load_tasks(temp_dir)[0]['name'], 'New name')


    def test_task_upsert_unknown_id(self):
        with create_test_files([]) as temp_dir:
            with self.assertRaises(ValueError):
                task_upsert(temp_dir, 'nope', 'N', parse_task_time('09:00'), [1], 'p', 'llm')


    def test_task_upsert_bad_fields(self):
        with create_test_files([]) as temp_dir:
            with self.assertRaises(ValueError):
                task_upsert(temp_dir, None, '   ', parse_task_time('09:00'), [1], 'p', 'llm')
            with self.assertRaises(ValueError):
                task_upsert(temp_dir, None, 'N', parse_task_time('09:00'), [1], 'p', '')
            with self.assertRaises(ValueError):
                task_upsert(temp_dir, None, 'N', parse_task_time('09:00'), [1], 'p', 'llm', num_ctx='bad')
            with self.assertRaises(ValueError):
                task_upsert(temp_dir, None, 'N', parse_task_time('09:00'), [1], 'p', 'llm', num_ctx=-5)
            with self.assertRaises(ValueError):
                task_upsert(temp_dir, None, 'N', parse_task_time('09:00'), [1], 'p', 'llm', tools='unknown_tool')


    def test_task_log_text(self):
        with create_test_files([
            ('logs/2026-02-02.log', '09:00 ERROR task "a": boom\n09:05 INFO task "b": fine\n'),
            ('logs/2026-02-03.log', '10:00 ERROR task "a": again\n')
        ]) as temp_dir:
            self.assertEqual( \
                task_log_text(temp_dir, 'a'), \
                '2026-02-03 10:00 ERROR task "a": again\n2026-02-02 09:00 ERROR task "a": boom' \
            )
            self.assertIsNone(task_log_text(temp_dir, 'missing'))
        with create_test_files([]) as temp_dir:
            self.assertIsNone(task_log_text(temp_dir, 'a'))


    def test_task_log_text_max_lines(self):
        # More log lines than max_lines - with the newest-first ordering only the newest lines show
        lines = '\n'.join(f'10:{minute:02d}:00 OK task "a": line {minute}' for minute in range(10))
        with create_test_files([('logs/2026-02-03.log', lines + '\n')]) as temp_dir:
            self.assertEqual( \
                task_log_text(temp_dir, 'a', max_lines=3), \
                '2026-02-03 10:09:00 OK task "a": line 9\n' \
                '2026-02-03 10:08:00 OK task "a": line 8\n' \
                '2026-02-03 10:07:00 OK task "a": line 7' \
            )


class TestTaskManager(unittest.TestCase):

    def test_init_with_tasks_starts(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            with unittest.mock.patch('threading.Thread') as mock_thread:
                mock_task_manager = TaskManager(app)
            mock_thread.assert_called_once_with(target=TaskManager.task_thread_fn, args=(mock_task_manager,))


    def test_init_without_tasks_does_not_start(self):
        app = TestApp({})
        with unittest.mock.patch('threading.Thread') as mock_thread:
            task_manager = TaskManager(app)
        self.assertFalse(task_manager.started)
        mock_thread.assert_not_called()


    def test_start_idempotent(self):
        app = TestApp({})
        task_manager = TaskManager(app)
        with unittest.mock.patch('threading.Thread') as mock_thread:
            task_manager.start()
            task_manager.start()
        mock_thread.assert_called_once_with(target=TaskManager.task_thread_fn, args=(task_manager,))


    def test_tick_due_task(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir, 'tasksCatchUp': True})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)  # within the catch-up window
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_called_once_with( \
                temp_dir, app.pool_manager, 'briefing', memory_limit=3000, now=now, \
                stop=unittest.mock.ANY \
            )


    def test_tick_no_catchup_default(self):
        # Without the tasksCatchUp config key, a missed slot (app was off) does not run at startup
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)  # outside the 2-tick window
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_not_called()


    def test_tick_recent_task(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 0, 29)  # within 2 scheduler ticks
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_called_once_with( \
                temp_dir, app.pool_manager, 'briefing', memory_limit=3000, now=now, \
                stop=unittest.mock.ANY \
            )


    def test_tick_already_run(self):
        with create_test_files([]) as temp_dir:
            task = dict(TEST_TASK, lastRun='2026-02-03 09:00')
            save_tasks(temp_dir, [task])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 1)
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_not_called()


    def test_tick_no_catchup(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir, 'tasksCatchUp': False})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)  # outside the 2-tick window
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_not_called()


    def test_tick_slot_beyond_catchup(self):
        # The task runs on Mondays only; now is Wednesday - the Monday slot is 2 days old
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [dict(TEST_TASK, days=[1])])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 4, 9, 10)
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_not_called()


    def test_tick_wrong_day(self):
        # The task runs on Saturdays only; now is Tuesday
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [dict(TEST_TASK, days=[6])])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_not_called()


    def test_tick_bad_task_does_not_raise(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [dict(TEST_TASK, time='bad')])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)
            task_manager.tick(now=now)  # must not raise


    def test_run_task_by_id(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.run_task_by_id('briefing')
            mock_run.assert_called_once_with( \
                temp_dir, app.pool_manager, 'briefing', memory_limit=3000, now=unittest.mock.ANY, \
                stop=unittest.mock.ANY \
            )


    def test_run_task_by_id_adds_task_conversation(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 30)
            with mock_ollama([[{'message': {'content': 'The report.'}}]], capabilities=['tools']):
                report = task_manager.run_task_by_id('briefing', now=now)
            self.assertEqual(report, 'The report.')
            conversations = app.config_dict['conversations']
            self.assertEqual(len(conversations), 1)
            conversation = conversations[0]
            self.assertEqual(conversation['taskId'], 'briefing')
            self.assertEqual(conversation['model'], 'llm')
            self.assertEqual(conversation['title'], 'Briefing 2026-02-03 09:30')
            self.assertEqual( \
                conversation['exchanges'], [{'user': 'Make a report', 'model': 'The report.'}] \
            )


    def test_run_task_by_id_failure_no_task_conversation(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [dict(TEST_TASK, model=None)])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            report = task_manager.run_task_by_id('briefing')
            self.assertIsNone(report)
            self.assertListEqual(app.config_dict['conversations'], [])


    def test_run_task_tracks_running_state(self):
        # While a task runs, task_running reports True (the tasks page's spinner); afterwards False
        with create_test_files([]) as temp_dir, \
             mock_ollama([[{'message': {'content': 'The report.'}}]], capabilities=['tools']):
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            outer_running = []

            def mock_run_stored(*_args, **_kwargs):
                outer_running.append(task_manager.task_running('briefing'))
                return 'The report.'

            with unittest.mock.patch('ollama_chat.tasks.run_stored_task', mock_run_stored):
                task_manager.run_task_by_id('briefing')
            self.assertIn(True, outer_running)
            self.assertFalse(task_manager.task_running('briefing'))


    def test_run_task_running_clears_on_exception(self):
        # A failed run still clears the task's running state
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task', side_effect=RuntimeError):
                self.assertRaises(RuntimeError, task_manager.run_task_by_id, 'briefing')
            self.assertFalse(task_manager.task_running('briefing'))


    def test_tick_adds_task_conversation(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir, 'tasksCatchUp': True})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)  # within the catch-up window
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                mock_run.return_value = 'The report.'
                task_manager.tick(now=now)
            conversation = app.config_dict['conversations'][0]
            self.assertEqual(conversation['taskId'], 'briefing')
            self.assertEqual(conversation['title'], 'Briefing 2026-02-03 09:10')
            self.assertEqual( \
                conversation['exchanges'], [{'user': 'Make a report', 'model': 'The report.'}] \
            )


    def test_tick_failure_no_task_conversation(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir, 'tasksCatchUp': True})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)  # within the catch-up window
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                mock_run.return_value = None
                task_manager.tick(now=now)
            self.assertListEqual(app.config_dict['conversations'], [])
