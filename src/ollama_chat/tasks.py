# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The ollama-chat scheduled task manager
"""

# pylint: disable=cyclic-import
# The tasks module and the chat module depend on each other's helpers. Both imports are
# lazy (function-level), so no actual import cycle occurs at run time.

import datetime
import json
import pathlib
import re
import threading
import types

from .memory import MEMORY_LIMIT_DEFAULT, memory_context, workspace_dir
from .ollama import ollama_chat, ollama_show


# The tools available to scheduled tasks - read-only tools only, for safety. Tools that write
# (like send_email) must never be added here unless explicitly made opt-in by the user.
TASK_TOOLS = ('web_search', 'fetch_page')


def _task_web_tools():
    # Imported inline to avoid a circular import with the chat module
    from .web_tools import WEB_TOOLS  # pylint: disable=import-outside-toplevel
    return WEB_TOOLS


# The workspace task and log file names
TASKS_FILENAME = 'tasks.json'
LOGS_DIRNAME = 'logs'

# The task schedule day-of-week presets. Days are ISO weekdays - Monday is 1, Sunday is 7.
TASK_DAY_PRESETS = {'all': [1, 2, 3, 4, 5, 6, 7], 'weekdays': [1, 2, 3, 4, 5], 'weekends': [6, 7]}
_TASK_DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

# The scheduler tick, in seconds
SCHEDULER_TICK = 30

# The missed-task catch-up window
CATCHUP_WINDOW = datetime.timedelta(hours=24)


# The workspace tasks.json path
def tasks_path(workspace):
    return pathlib.Path(workspace, TASKS_FILENAME)


# Load the workspace's task list, or [] when there is no (or an unreadable) tasks.json
def load_tasks(workspace):
    try:
        with open(tasks_path(workspace), 'r', encoding='utf-8') as tasks_fh:
            tasks = json.load(tasks_fh)
    except (OSError, ValueError, TypeError):
        return []
    return tasks if isinstance(tasks, list) else []


# Save the workspace's task list
def save_tasks(workspace, tasks):
    workspace_path = pathlib.Path(workspace)
    workspace_path.mkdir(parents=True, exist_ok=True)
    with open(tasks_path(workspace), 'w', encoding='utf-8') as tasks_fh:
        json.dump(tasks, tasks_fh, indent=4)


# Normalize a task's tools argument - None means the default read-only tools
def _task_tool_names(tools):
    if isinstance(tools, str):
        tool_names = [tool.strip() for tool in tools.split(',') if tool.strip()]
    else:
        tool_names = [tool.strip() for tool in (tools or TASK_TOOLS)]
    unknown_tools = [tool for tool in tool_names if tool not in TASK_TOOLS]
    if unknown_tools:
        raise ValueError(f'unknown or disallowed task tool(s): {", ".join(unknown_tools)}')
    return tool_names or list(TASK_TOOLS)


# Generate a new, unique task ID from the task's name
def task_id_new(name, tasks):
    task_id_base = (re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-') or 'task')
    suffix = 0
    while True:
        task_id = task_id_base + (f'-{suffix}' if suffix else '')
        if not any(task.get('id') == task_id for task in tasks):
            return task_id
        suffix += 1


# Parse a task's "HH:MM" schedule time
def parse_task_time(text):
    match = re.fullmatch(r'(\d{1,2}):(\d{2})', str(text).strip())
    if not match:
        raise ValueError(f'invalid time "{text}", expected "HH:MM"')
    hours, minutes = (int(match.group(1)), int(match.group(2)))
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        raise ValueError(f'invalid time "{text}", expected "HH:MM"')
    return datetime.time(hours, minutes)


# Parse a task's run days - 'all', 'weekdays', 'weekends', or a comma list of ISO weekdays
# (Monday is 1, Sunday is 7)
def parse_task_days(text):
    text = str(text).strip().lower()
    if text in TASK_DAY_PRESETS:
        return list(TASK_DAY_PRESETS[text])
    days = []
    for day_text in text.split(','):
        match = re.fullmatch(r'\s*([1-7])\s*', day_text)
        if not match:
            raise ValueError(f'invalid days "{text}", expected "all", "weekdays", "weekends", or "1,3,5"')
        day = int(match.group(1))
        if day not in days:
            days.append(day)
    if not days:
        raise ValueError(f'invalid days "{text}"')
    return sorted(days)


# Textual description of a task's run days
def task_days_text(days):
    if not days:
        return 'never'
    if sorted(days) == TASK_DAY_PRESETS['all']:
        return 'every day'
    return ', '.join(_TASK_DAY_NAMES[day - 1] for day in sorted(days))


# Textual summary of the task list, for the /tasks command reply
def tasks_summary(tasks):
    if not tasks:
        return 'There are no scheduled tasks.'
    lines = ['Tasks:']
    for ix, task in enumerate(tasks):
        line = \
            f'{ix + 1}. {task.get("id", "")} - "{task.get("name", "")}" - ' \
            f'{task.get("time", "")} {task_days_text(task.get("days"))} - model {task.get("model", "")}'
        if task.get('lastRun'):
            line += f' - last run {task["lastRun"]}'
        if task.get('lastError'):
            line += f' - ERROR: {task["lastError"]}'
        lines.append(line)
    return '\n'.join(lines)


# Add a task to the workspace's task list, returning the new task's ID
def task_add(workspace, name, run_time, days, prompt, model, num_ctx=None, tools=None, dest='daily'):
    tasks = load_tasks(workspace)
    tool_names = _task_tool_names(tools)
    task = {
        'id': task_id_new(name, tasks),
        'name': name,
        'time': run_time.strftime('%H:%M'),
        'days': sorted(days),
        'prompt': prompt,
        'model': model,
        'num_ctx': num_ctx,
        'tools': tool_names,
        'dest': dest,
        'lastRun': None,
        'lastError': None
    }
    tasks.append(task)
    save_tasks(workspace, tasks)
    return task['id']


# Remove a task from the workspace's task list by ID
def task_remove(workspace, task_id):
    tasks = load_tasks(workspace)
    tasks_new = [task for task in tasks if task.get('id') != task_id]
    if len(tasks_new) == len(tasks):
        raise ValueError(f'No task "{task_id}"')
    save_tasks(workspace, tasks_new)


# A task's most recent scheduled run on or before "now"
def task_last_slot(task, now):
    run_time = parse_task_time(task.get('time', ''))
    days = task.get('days')
    if days is None:
        days = TASK_DAY_PRESETS['all']
    for days_back in range(8):
        day = now.date() - datetime.timedelta(days=days_back)
        if day.isoweekday() not in days:
            continue
        slot = datetime.datetime.combine(day, run_time)
        if slot <= now:
            return slot
    return None


# Run a task by ID, updating lastRun/lastError and saving tasks.json. Returns the report text.
# Used both by the app's scheduler and by the standalone run_task.py script.
def run_stored_task(workspace, pool_manager, task_id, memory_limit=MEMORY_LIMIT_DEFAULT, now=None):
    tasks = load_tasks(workspace)
    task = next((task_search for task_search in tasks if task_search.get('id') == task_id), None)
    if task is None:
        raise ValueError(f'No task "{task_id}"')

    now = datetime.datetime.now() if now is None else now
    report = None
    try:
        report = _run_task(pool_manager, workspace, task, memory_limit=memory_limit, now=now)
        write_task_result(workspace, task, now, report)
        task['lastError'] = None
    except Exception as exc:
        log_task_error(workspace, task_id, exc, now=now)
        task['lastError'] = str(exc)

    task['lastRun'] = now.strftime('%Y-%m-%d %H:%M')
    save_tasks(workspace, tasks)
    return report


# Run a single task: generate the report with the tool-calling chat loop. (Never raises.)
def run_task_once(pool_manager, workspace, task, memory_limit=MEMORY_LIMIT_DEFAULT, now=None):
    # Imported inline to avoid a circular import with the chat module
    from .chat import _MAX_TOOL_ROUNDS, _StreamTokenFilter, _run_tool, _tool_call_arguments  # pylint: disable=import-outside-toplevel

    try:
        return _run_task(pool_manager, workspace, task, memory_limit=memory_limit, now=now)
    except Exception as exc:
        log_task_error(workspace, str(task.get('id', '')), exc, now=now)
        return None


# Run a single task, raising exceptions on failure
def _run_task(pool_manager, workspace, task, memory_limit=MEMORY_LIMIT_DEFAULT, now=None):
    # Imported inline to avoid a circular import with the chat module
    from .chat import _MAX_TOOL_ROUNDS, _StreamTokenFilter, _run_tool, _tool_call_arguments  # pylint: disable=import-outside-toplevel

    now = datetime.datetime.now() if now is None else now

    # The model
    model = task.get('model')
    if not model:
        raise ValueError(f'task "{task["id"]}" has no model')

    # The messages - workspace memory context plus the task prompt
    prompt = str(task.get('prompt') or '')
    messages = []
    memory_text = memory_context(workspace, prompt, memory_limit)
    if memory_text:
        messages.append({'role': 'system', 'content': memory_text})
    messages.append({'role': 'user', 'content': prompt})

    # The task's allowed tools (read-only tools only) - unused when the model can't tool-call
    request_tools = _task_tool_list(pool_manager, model, task.get('tools') or [])

    # Generate the report using the chat tool-calling loop
    chat_shim = types.SimpleNamespace(app=types.SimpleNamespace(pool_manager=pool_manager))
    tool_rounds = 0
    while True:
        round_tools = request_tools if request_tools is None or tool_rounds < _MAX_TOOL_ROUNDS else None

        # Stream this round's response, collecting the model's tool calls
        content_filter = _StreamTokenFilter()
        round_content = ''
        tool_calls = []
        for chunk in ollama_chat( \
            pool_manager, model, messages, think=False, tools=round_tools, num_ctx=task.get('num_ctx') \
        ):
            message = chunk.get('message') or {}
            if message.get('content'):
                round_content += content_filter.add(message['content'])
            if message.get('tool_calls'):
                tool_calls.extend(message['tool_calls'])
        if not tool_calls or round_tools is None:
            return round_content

        # Execute the tool calls and add their results to the messages
        tool_rounds += 1
        messages.append({'role': 'assistant', 'content': round_content, 'tool_calls': tool_calls})
        for tool_call in tool_calls:
            tool_name, arguments = _tool_call_arguments(tool_call)
            tool_content, _tool_event = _run_tool(chat_shim, tool_name, arguments)
            messages.append({'role': 'tool', 'tool_name': tool_name, 'content': tool_content})


# A task's tool argument list, as passed to ollama_chat (only the task's allowed, read-only tools)
def _task_tool_list(pool_manager, model, tool_names):
    tool_names = [tool for tool in tool_names if tool in TASK_TOOLS]
    if not tool_names:
        return None
    model_show = ollama_show(pool_manager, model)
    if 'tools' not in (model_show.get('capabilities') or []):
        return None
    return [tool for tool in _task_web_tools() if tool['function']['name'] in tool_names]


# Write a single task's report to the daily memory file (memory/daily/YYYY-MM-DD.md)
def write_task_result(workspace, task, now, report):
    daily_dir = pathlib.Path(workspace, 'memory', 'daily')
    daily_dir.mkdir(parents=True, exist_ok=True)
    with open(daily_dir / f'{now:%Y-%m-%d}.md', 'a', encoding='utf-8') as daily_fh:
        daily_fh.write(
            f'\n## {task["name"]} ({now:%H:%M})\n\n'
            + report.strip()
            + '\n'
        )


# Log a task error to workspace/logs/YYYY-MM-DD.log
def log_task_error(workspace, task_id, error, now=None):
    now = datetime.datetime.now() if now is None else now
    logs_dir = pathlib.Path(workspace, LOGS_DIRNAME)
    logs_dir.mkdir(parents=True, exist_ok=True)
    with open(logs_dir / f'{now:%Y-%m-%d}.log', 'a', encoding='utf-8') as logs_fh:
        logs_fh.write(f'{now:%H:%M:%S} ERROR task "{task_id}": {error}\n')


# The scheduled task manager, running tasks due on their schedule
class TaskManager():
    __slots__ = ('app', 'started')


    def __init__(self, app):
        self.app = app
        self.started = False

        # Start the scheduler thread when the workspace already has tasks - otherwise the
        # thread starts lazily, when a task is added
        with app.config() as config:
            tasks = load_tasks(workspace_dir(config))
        if tasks:
            self.start()


    # Start the scheduler thread, if not already running
    def start(self):
        if self.started:
            return
        self.started = True
        thread = threading.Thread(target=TaskManager.task_thread_fn, args=(self,))
        thread.daemon = True
        thread.start()


    @staticmethod
    def task_thread_fn(task_manager):
        while True:
            task_manager.tick()
            threading.Event().wait(SCHEDULER_TICK)


    # Run a task by ID now (e.g. from the /task run command), updating lastRun/lastError
    def run_task_by_id(self, task_id):
        with self.app.config() as config:
            workspace = str(workspace_dir(config))
            memory_limit = config.get('memoryLimit', MEMORY_LIMIT_DEFAULT)
        return run_stored_task(workspace, self.app.pool_manager, task_id, memory_limit=memory_limit)


    # Run all due tasks. The "now" and "catchup" arguments are for unit tests.
    def tick(self, now=None, catchup=None):
        now = datetime.datetime.now() if now is None else now
        with self.app.config() as config:
            workspace = str(workspace_dir(config))
            memory_limit = config.get('memoryLimit', MEMORY_LIMIT_DEFAULT)
            if catchup is None:
                catchup = config.get('tasksCatchUp', True)

        tasks = load_tasks(workspace)
        for task in tasks:
            try:
                self._tick_task(workspace, task, now, memory_limit, catchup)
            except Exception: # pylint: disable=broad-exception-caught
                pass


    # Run a single task if its scheduled time has came (and it hasn't already run for the slot)
    def _tick_task(self, workspace, task, now, memory_limit, catchup):
        slot = task_last_slot(task, now)
        if slot is None:
            return

        # Already ran for this slot?
        last_run_text = task.get('lastRun')
        if last_run_text:
            try:
                if datetime.datetime.strptime(last_run_text, '%Y-%m-%d %H:%M') >= slot:
                    return
            except ValueError:
                pass

        # Run now, catch up on missed runs within the catch-up window, or wait for the next
        # scheduled run
        delta = now - slot
        if not (delta <= datetime.timedelta(seconds=2 * SCHEDULER_TICK) or (catchup and delta <= CATCHUP_WINDOW)):
            return
        run_stored_task(workspace, self.app.pool_manager, task['id'], memory_limit=memory_limit, now=now)
