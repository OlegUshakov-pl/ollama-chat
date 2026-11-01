# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

from contextlib import contextmanager
import datetime
import json
import os
import unittest
import unittest.mock

from ollama_chat.memory import ensure_workspace
from ollama_chat.tasks import (
    TASK_TOOLS, _run_task,
    load_tasks, log_task_error, parse_task_days, parse_task_time, run_stored_task, run_task_once,
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
    def config(self, _save=False):
        yield self.config_dict


TEST_TASK = {
    'id': 'briefing',
    'name': 'Briefing',
    'time': '09:00',
    'days': [1, 2, 3, 4, 5, 6, 7],
    'prompt': 'Make a report',
    'model': 'llm',
    'num_ctx': None,
    'tools': ['web_search', 'fetch_page'],
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
                    'tools': list(TASK_TOOLS),
                    'dest': 'daily',
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


    def test_task_add_unknown_tool(self):
        with create_test_files([]) as temp_dir:
            with self.assertRaises(ValueError) as caught:
                task_add(temp_dir, 'T', parse_task_time('09:00'), parse_task_days('all'), 'p', 'llm', tools='send_email')
            self.assertIn('send_email', str(caught.exception))
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


    def test_run_task_no_tools_capability(self):
        with create_test_files([]) as temp_dir:
            ensure_workspace(temp_dir)
            task = dict(TEST_TASK)  # tools: web_search, fetch_page

            # The model can't tool-call, so the tools argument is null
            with mock_ollama([[{'message': {'content': 'The report.'}}]], capabilities=[]) as (mock_chat, _mock_show):
                report = _run_task(unittest.mock.sentinel.pool, temp_dir, task)
            self.assertEqual(report, 'The report.')
            self.assertIsNone(mock_chat.call_args.kwargs.get('tools'))


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
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 10)  # within the catch-up window
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_called_once_with( \
                temp_dir, app.pool_manager, 'briefing', memory_limit=3000, now=now \
            )


    def test_tick_recent_task(self):
        with create_test_files([]) as temp_dir:
            save_tasks(temp_dir, [TEST_TASK])
            app = TestApp({'conversations': [], 'workspace': temp_dir})
            task_manager = make_task_manager(app)
            now = datetime.datetime(2026, 2, 3, 9, 0, 29)  # within 2 scheduler ticks
            with unittest.mock.patch('ollama_chat.tasks.run_stored_task') as mock_run:
                task_manager.tick(now=now)
            mock_run.assert_called_once_with( \
                temp_dir, app.pool_manager, 'briefing', memory_limit=3000, now=now \
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
                temp_dir, app.pool_manager, 'briefing', memory_limit=3000 \
            )
