# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The ollama-chat back-end application
"""

from contextlib import contextmanager
import copy
import ctypes
import datetime
import json
import os
import pathlib
from functools import partial
import platform
import importlib.resources
import re
import threading
import uuid

import chisel
import urllib3
import schema_markdown

from .chat import ChatManager, config_conversation, config_template_prompts
from .email_tools import (
    get_email_settings, save_email_settings, send_email as smtp_send_email, test_email_connection
)
from .memory import (
    MEMORY_BACKUP_SUFFIX, MEMORY_FILENAME, PROFILE_LIMIT_DEFAULT, USER_MEMORY_FILENAME,
    daily_file_path, ensure_workspace, memory_file_path, read_memory_file, workspace_dir,
    write_memory_file
)
from .ollama import ollama_delete, ollama_list, ollama_pull
from .pdf import conversation_markdown, write_pdf_file
from .tasks import (
    TaskManager, load_tasks, parse_task_time, task_enabled, task_log_text, task_remove, task_upsert
)


# The ollama-chat back-end API WSGI application class
class OllamaChat(chisel.Application):
    __slots__ = ('config', 'xorigin', 'chats', 'downloads', 'download_error', 'pool_manager', 'tasks')


    def __init__(self, config_path, xorigin=False):
        super().__init__()
        self.config = ConfigManager(config_path)
        self.xorigin = xorigin
        self.chats = {}
        self.downloads = {}
        self.download_error = None
        self.pool_manager = urllib3.PoolManager(num_pools=10, maxsize=10)
        self.tasks = TaskManager(self)

        # Back-end documentation
        self.add_requests(chisel.create_doc_requests())

        # Back-end APIs
        self.add_request(create_template)
        self.add_request(delete_conversation)
        self.add_request(delete_conversation_exchange)
        self.add_request(delete_model)
        self.add_request(delete_task)
        self.add_request(delete_template)
        self.add_request(download_model)
        self.add_request(export_pdf)
        self.add_request(get_conversation)
        self.add_request(get_conversations)
        self.add_request(get_models)
        self.add_request(get_profile)
        self.add_request(get_settings)
        self.add_request(get_system_info)
        self.add_request(get_task_log)
        self.add_request(get_tasks)
        self.add_request(get_template)
        self.add_request(move_conversation)
        self.add_request(move_template)
        self.add_request(regenerate_conversation_exchange)
        self.add_request(reply_conversation)
        self.add_request(run_task)
        self.add_request(send_email_request)
        self.add_request(set_conversation_title)
        self.add_request(set_email_settings)
        self.add_request(set_model)
        self.add_request(set_profile)
        self.add_request(set_task)
        self.add_request(set_workspace)
        self.add_request(start_conversation)
        self.add_request(start_template)
        self.add_request(stop_conversation)
        self.add_request(stop_model_download)
        self.add_request(test_email_connection_request)
        self.add_request(update_template)

        # Front-end statics
        self.add_static('index.html', urls=(('GET', None), ('GET', '/')))
        self.add_static('app.css')
        self.add_static('app.js')
        self.add_static('vendor/marked.min.js')
        self.add_static('vendor/purify.min.js')
        self.add_static('ollamaChat.bare')
        self.add_static('ollamaChatConversation.bare')
        self.add_static('ollamaChatModels.bare')
        self.add_static('ollamaChatTemplate.bare')
        self.add_static('ollamaChatUtil.bare')


    def add_static(self, filename, urls=(('GET', None),), doc_group='Ollama Chat Statics'):
        content_type = _CONTENT_TYPES.get(os.path.splitext(filename)[1], 'text/plain; charset=utf-8')
        with importlib.resources.files('ollama_chat.static').joinpath(filename).open('rb') as fh:
            self.add_request(chisel.StaticRequest(filename, fh.read(), content_type, urls, doc_group=doc_group))


    def __call__(self, environ, start_response):
        if self.xorigin:
            return super().__call__(environ, partial(_start_response_xorigin, start_response))
        return super().__call__(environ, start_response)


def _start_response_xorigin(start_response, status, headers):
    headers_inner = list(headers)
    headers_inner.append(('Access-Control-Allow-Origin', '*'))
    start_response(status, headers_inner)


_CONTENT_TYPES = {
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.svg': 'image/svg+xml'
}


# The ollama-chat configuration context manager
class ConfigManager:
    __slots__ = ('config_path', 'config_lock', 'config')


    def __init__(self, config_path):
        self.config_path = config_path
        self.config_lock = threading.Lock()

        # Ensure the config file exists with default config if it doesn't exist
        if os.path.isfile(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as fh_config:
                self.config = schema_markdown.validate_type(OLLAMA_CHAT_TYPES, 'OllamaChatConfig', json.loads(fh_config.read()))
        else:
            self.config = {'conversations': []}


    @contextmanager
    def __call__(self, save=False):
        # Acquire the config lock
        self.config_lock.acquire()

        try:
            # Yield the config on context entry
            yield self.config

            # Save the config file on context exit, if requested
            if save and not self.config.get('noSave'):
                with open(self.config_path, 'w', encoding='utf-8') as fh_config:
                    json.dump(self.config, fh_config, indent=4, sort_keys = True)
        finally:
            # Release the config lock
            self.config_lock.release()


# The model download manager class
class DownloadManager():
    __slots__ = ('app', 'model', 'status', 'completed', 'total', 'stop')


    def __init__(self, app, model):
        self.app = app
        self.model = model
        self.status = ''
        self.completed = 0
        self.total = 0
        self.stop = False

        # Start the download thread
        download_thread = threading.Thread(target=self.download_thread_fn, args=(self, app.pool_manager))
        download_thread.daemon = True
        download_thread.start()


    @staticmethod
    def download_thread_fn(manager, pool_manager):
        error = None
        try:
            for progress in ollama_pull(pool_manager, manager.model):
                # Stopped?
                if manager.stop:
                    break

                # Update the download status
                manager.status = progress['status']
                manager.completed = progress.get('completed', 0)
                manager.total = progress.get('total')

        except Exception as exc:
            error = str(exc)

        # Delete the application's download entry (under the config lock, and only if it's still ours)
        with manager.app.config():
            if manager.app.downloads.get(manager.model) is manager:
                del manager.app.downloads[manager.model]
            if error:
                manager.app.download_error = error


# The Ollama Chat API type model
with importlib.resources.files('ollama_chat.static').joinpath('ollamaChat.smd').open('r') as cm_smd:
    OLLAMA_CHAT_TYPES = schema_markdown.parse_schema_markdown(cm_smd.read())


@chisel.action(name='getConversations', types=OLLAMA_CHAT_TYPES)
def get_conversations(ctx, unused_req):
    with ctx.app.config() as config:
        response = {
            'workspace': str(workspace_dir(config)),
            'conversations': [
                {
                    'id': conversation['id'],
                    'model': conversation['model'],
                    'title': conversation['title'],
                    'generating': conversation['id'] in ctx.app.chats
                }
                for conversation in config['conversations']
            ],
            'templates': [] if 'templates' not in config else [
                {
                    'id': template['id'],
                    'title': template['title']
                }
                for template in config['templates']
            ],
            'tasks': [
                {
                    'id': task.get('id', ''),
                    'name': task.get('name', ''),
                    'time': task.get('time', ''),
                    'days': task.get('days') or [],
                    'model': task.get('model', '')
                }
                for task in load_tasks(workspace_dir(config))
            ]
        }
        if 'model' in config:
            response['model'] = config['model']
        return response


@chisel.action(name='setModel', types=OLLAMA_CHAT_TYPES)
def set_model(ctx, req):
    with ctx.app.config(save=True) as config:
        config['model'] = req['model']


# Set the workspace directory, creating it (and its memory directory) if it doesn't exist
@chisel.action(name='setWorkspace', types=OLLAMA_CHAT_TYPES)
def set_workspace(ctx, req):
    workspace = pathlib.Path(req['path']).expanduser()
    try:
        ensure_workspace(workspace)
    except OSError as exc:
        raise chisel.ActionError('BadWorkspace', f'Failed to create workspace "{req["path"]}" ({exc})') from None

    # Resolve a relative path to an absolute path for display
    with ctx.app.config(save=True) as config:
        config['workspace'] = str(workspace.resolve())
        return {'workspace': str(workspace_dir(config))}


# Get the workspace and email settings - the app password is never included
@chisel.action(name='getSettings', types=OLLAMA_CHAT_TYPES)
def get_settings(ctx, unused_req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
        return {
            'workspace': workspace,
            'email': get_email_settings(workspace)
        }


# Save the email settings to the workspace's .env file. The app password is write-only - an
# empty "password" keeps the saved password, and the password is never sent to the browser.
@chisel.action(name='setEmailSettings', types=OLLAMA_CHAT_TYPES)
def set_email_settings(ctx, req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
    try:
        save_email_settings( \
            workspace, \
            req['imapHost'], \
            req.get('imapPort', 993), \
            req['smtpHost'], \
            req.get('smtpPort', 465), \
            req['user'], \
            password=req.get('password') or None
        )
    except OSError as exc:
        raise chisel.ActionError('BadEmailSettings', f'Failed to save the email settings ({exc})') from None
    return {'saved': True}


# Check the email settings - log in to the configured IMAP and SMTP servers, sending nothing
@chisel.action(name='testEmailConnection', types=OLLAMA_CHAT_TYPES)
def test_email_connection_request(ctx, unused_req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
    try:
        message = test_email_connection(workspace)
    except ValueError as exc:
        raise chisel.ActionError('TestFailed', str(exc)) from None
    return {'message': message}


# Get the user profile - the USER.md content and the profile character limit
@chisel.action(name='getProfile', types=OLLAMA_CHAT_TYPES)
def get_profile(ctx, unused_req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
        limit = config.get('profileLimit', PROFILE_LIMIT_DEFAULT)
    return {'content': read_memory_file(workspace, USER_MEMORY_FILENAME), 'limit': limit}


# Save the user profile (memory/USER.md). The content is limited to profileLimit characters.
@chisel.action(name='setProfile', types=OLLAMA_CHAT_TYPES)
def set_profile(ctx, req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
        limit = config.get('profileLimit', PROFILE_LIMIT_DEFAULT)
    content = req['content']
    if len(content) > limit:
        raise chisel.ActionError( \
            'ProfileTooLong', \
            f'The profile is too long - {len(content)} characters (the limit is {limit})'
        )
    try:
        write_memory_file(workspace, USER_MEMORY_FILENAME, content)
    except (OSError, ValueError) as exc:
        raise chisel.ActionError('BadProfile', f'Failed to save the profile ({exc})') from None
    return {'saved': True}


# Get the tasks' full info, for the tasks page
@chisel.action(name='getTasks', types=OLLAMA_CHAT_TYPES)
def get_tasks(ctx, unused_req):
    with ctx.app.config() as config:
        tasks = load_tasks(workspace_dir(config))
    return {'tasks': [_task_details(task) for task in tasks]}


# A task dict's full info response
def _task_details(task):
    details = {
        'id': task.get('id', ''),
        'name': task.get('name', ''),
        'time': task.get('time', ''),
        'days': task.get('days') or [],
        'model': task.get('model', ''),
        'prompt': str(task.get('prompt') or ''),
        'tools': task.get('tools') or [],
        'enabled': task_enabled(task)
    }
    if task.get('lastRun'):
        details['lastRun'] = task['lastRun']
    if task.get('lastError'):
        details['lastError'] = task['lastError']
    if task.get('num_ctx'):
        details['numCtx'] = task['num_ctx']
    return details


# Create a scheduled task, or update the task's fields when "id" is present
@chisel.action(name='setTask', types=OLLAMA_CHAT_TYPES)
def set_task(ctx, req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
    days = req['days']
    if not days or not all(isinstance(day, int) and 1 <= day <= 7 for day in days):
        raise chisel.ActionError('BadTask', 'the task days must be ISO weekdays 1-7')
    try:
        task = task_upsert( \
            workspace, \
            req.get('id'), \
            req['name'], \
            parse_task_time(req['time']), \
            sorted(set(days)), \
            req['prompt'], \
            req['model'], \
            num_ctx=req.get('numCtx'), \
            tools=req['tools'], \
            enabled=req.get('enabled', True)
        )
    except ValueError as exc:
        raise chisel.ActionError('BadTask', str(exc)) from None

    # Start the scheduler thread when not already running (it starts lazily)
    ctx.app.tasks.start()
    return {'id': task['id']}


# Delete a scheduled task
@chisel.action(name='deleteTask', types=OLLAMA_CHAT_TYPES)
def delete_task(ctx, req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
    try:
        task_remove(workspace, req['id'])
    except ValueError as exc:
        raise chisel.ActionError('UnknownTaskID', str(exc)) from None


# Run a scheduled task now, in a background thread. Poll getTasks for the task's lastRun.
@chisel.action(name='runTask', types=OLLAMA_CHAT_TYPES)
def run_task(ctx, req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
    task_id = req['id']
    if not any(task.get('id') == task_id for task in load_tasks(workspace)):
        raise chisel.ActionError('UnknownTaskID', f'No task "{task_id}"')
    threading.Thread(target=ctx.app.tasks.run_task_by_id, args=(task_id,), daemon=True).start()
    return {'started': True}


# Get a scheduled task's run log, from the workspace's logs directory
@chisel.action(name='getTaskLog', types=OLLAMA_CHAT_TYPES)
def get_task_log(ctx, req):
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
    task_id = req['id']
    if not any(task.get('id') == task_id for task in load_tasks(workspace)):
        raise chisel.ActionError('UnknownTaskID', f'No task "{task_id}"')
    response = {}
    log = task_log_text(workspace, task_id)
    if log:
        response['log'] = log
    return response


@chisel.action(name='moveConversation', types=OLLAMA_CHAT_TYPES)
def move_conversation(ctx, req):
    with ctx.app.config(save=True) as config:
        # Find the conversation index
        id_ = req['id']
        conversations = config['conversations']
        ix_conv = next((ix for ix, conv in enumerate(conversations) if conv['id'] == id_), None)
        if ix_conv is None:
            raise chisel.ActionError('UnknownConversationID')
        conversation = conversations[ix_conv]

        # Move down?
        if req['down']:
            if ix_conv < len(conversations) - 1:
                conversations[ix_conv] = conversations[ix_conv + 1]
                conversations[ix_conv + 1] = conversation
        else:
            if ix_conv > 0:
                conversations[ix_conv] = conversations[ix_conv - 1]
                conversations[ix_conv - 1] = conversation


@chisel.action(name='moveTemplate', types=OLLAMA_CHAT_TYPES)
def move_template(ctx, req):
    with ctx.app.config(save=True) as config:
        # Find the template index
        id_ = req['id']
        templates = config.get('templates') or []
        ix_tmpl = next((ix for ix, tmpl in enumerate(templates) if tmpl['id'] == id_), None)
        if ix_tmpl is None:
            raise chisel.ActionError('UnknownTemplateID')
        template = templates[ix_tmpl]

        # Move down?
        if req['down']:
            if ix_tmpl < len(templates) - 1:
                templates[ix_tmpl] = templates[ix_tmpl + 1]
                templates[ix_tmpl + 1] = template
        else:
            if ix_tmpl > 0:
                templates[ix_tmpl] = templates[ix_tmpl - 1]
                templates[ix_tmpl - 1] = template


@chisel.action(name='deleteTemplate', types=OLLAMA_CHAT_TYPES)
def delete_template(ctx, req):
    with ctx.app.config(save=True) as config:
        id_ = req['id']
        templates = config.get('templates') or []
        ix_tmpl = next((ix for ix, tmpl in enumerate(templates) if tmpl['id'] == id_), None)
        if ix_tmpl is None:
            raise chisel.ActionError('UnknownTemplateID')
        del templates[ix_tmpl]


@chisel.action(name='getTemplate', types=OLLAMA_CHAT_TYPES)
def get_template(ctx, req):
    template_id = req['id']
    with ctx.app.config() as config:
        templates = config.get('templates') or []
        template = next((template for template in templates if template['id'] == template_id), None)
        if template is None:
            raise chisel.ActionError('UnknownTemplateID')
        return copy.deepcopy(template)


@chisel.action(name='updateTemplate', types=OLLAMA_CHAT_TYPES)
def update_template(ctx, req):
    template_id = req['id']
    with ctx.app.config(save=True) as config:
        templates = config.get('templates') or []
        ix_template = next((ix_tmpl for ix_tmpl, tmpl in enumerate(templates) if tmpl['id'] == template_id), None)
        if ix_template is None:
            raise chisel.ActionError('UnknownTemplateID')
        templates[ix_template] = req


@chisel.action(name='startConversation', types=OLLAMA_CHAT_TYPES)
def start_conversation(ctx, req):
    with ctx.app.config() as config:
        # Compute the conversation title
        user_prompt = req['user']
        max_title_len = 50
        title = re.sub(r'\s+', ' ', user_prompt).strip()
        if len(title) > max_title_len:
            title_suffix = '...'
            title = f'{title[:max_title_len - len(title_suffix)]}{title_suffix}'

        # Create the new conversation object
        model = req.get('model', config.get('model'))
        if model is None:
            raise chisel.ActionError('NoModel')
        id_ = str(uuid.uuid4())
        conversation = {'id': id_, 'model': model, 'title': title, 'exchanges': []}

        # Add the new conversation to the application config
        config['conversations'].insert(0, conversation)

        # Start the model chat
        ctx.app.chats[id_] = ChatManager(
            ctx.app, id_, [user_prompt],
            think=req.get('think', False), files=req.get('files'),
            search=req.get('search', False), email=req.get('email', False)
        )

        # Return the new conversation identifier
        return {'id': id_}


@chisel.action(name='startTemplate', types=OLLAMA_CHAT_TYPES)
def start_template(ctx, req):
    template_id = req['id']
    variable_values = req.get('variables') or {}

    with ctx.app.config() as config:
        # Get the conversation template
        templates = config.get('templates') or []
        template = next((template for template in templates if template['id'] == template_id), None)
        if template is None:
            template = next((template for template in templates if template.get('name') == template_id), None)
        if template is None:
            raise chisel.ActionError('UnknownTemplateID', f'Unknown template "{template_id}"')

        # Get the template prompts
        try:
            title, prompts = config_template_prompts(template, variable_values)
        except ValueError as exc:
            message = str(exc)
            error = 'UnknownVariable' if message.startswith('unknown') else 'MissingVariable'
            raise chisel.ActionError(error, message)

        # Create the new conversation object
        model = req.get('model', config.get('model'))
        if model is None:
            raise chisel.ActionError('NoModel')
        id_ = str(uuid.uuid4())
        conversation = {'id': id_, 'model': model, 'title': title, 'exchanges': []}

        # Add the new conversation to the application config
        config['conversations'].insert(0, conversation)

        # Start the model chat
        ctx.app.chats[id_] = ChatManager(
            ctx.app, id_, prompts,
            think=req.get('think', False), files=req.get('files'), search=req.get('search', False), email=req.get('email', False)
        )

        # Return the new conversation identifier
        return {'id': id_}


@chisel.action(name='stopConversation', types=OLLAMA_CHAT_TYPES)
def stop_conversation(ctx, req):
    with ctx.app.config() as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Not generating?
        chat = ctx.app.chats.get(id_)
        if chat is None:
            return

        # Stop the conversation
        chat.stop = True
        del ctx.app.chats[id_]


@chisel.action(name='getConversation', types=OLLAMA_CHAT_TYPES)
def get_conversation(ctx, req):
    with ctx.app.config() as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Add the generating status
        conversation = copy.deepcopy(conversation)
        conversation['generating'] = id_ in ctx.app.chats

        # Return the conversation
        return {
            'conversation': conversation
        }


# Export a conversation or workspace memory file as PDF, writing it into the workspace's
# exports directory
@chisel.action(name='exportPdf', types=OLLAMA_CHAT_TYPES)
def export_pdf(ctx, req):
    # The markdown to export and its title, used for the PDF file name
    id_ = req.get('id')
    with ctx.app.config() as config:
        workspace = str(workspace_dir(config))
        if id_ is not None:
            conversation = config_conversation(config, id_)
            if conversation is None:
                raise chisel.ActionError('UnknownConversationID')
            (markdown_text, title) = (conversation_markdown(conversation), conversation['title'])
        else:
            (markdown_text, title) = _export_memory_markdown(req, workspace)

    # Write the PDF into the workspace's exports directory
    path = write_pdf_file(workspace, markdown_text, title)
    return {'file': str(path)}


# The PDF markdown of a workspace memory file - USER.md, MEMORY.md (or backup) or
# memory/daily/YYYY-MM-DD.md. Returns (markdown text, title), raising UnknownFile otherwise.
def _export_memory_markdown(req, workspace):
    file_name = req.get('file')
    if file_name is None:
        raise chisel.ActionError('UnknownFile', 'One of "id" or "file" must be specified')

    # Compute the memory file path, validating the file name
    match = re.fullmatch(r'daily/(\d{4}-\d{2}-\d{2})\.md', file_name)
    if match:
        try:
            date = datetime.date.fromisoformat(match.group(1))
        except ValueError:
            raise chisel.ActionError('UnknownFile', f'Unknown memory file "{file_name}"') from None
        path = daily_file_path(workspace, date)
    elif file_name in (USER_MEMORY_FILENAME, MEMORY_FILENAME, MEMORY_FILENAME + MEMORY_BACKUP_SUFFIX):
        path = memory_file_path(workspace, file_name)
    else:
        raise chisel.ActionError('UnknownFile', f'Unknown memory file "{file_name}"')

    # The PDF markdown - a file-name heading plus the file content
    try:
        with open(path, 'r', encoding='utf-8') as memory_fh:
            contents = memory_fh.read()
    except OSError:
        raise chisel.ActionError('UnknownFile', f'No memory file "{file_name}"') from None
    return (f'# {file_name}\n\n{contents}', file_name)


@chisel.action(name='replyConversation', types=OLLAMA_CHAT_TYPES)
def reply_conversation(ctx, req):
    with ctx.app.config() as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Busy?
        if id_ in ctx.app.chats:
            raise chisel.ActionError('ConversationBusy')

        # Start the model chat
        ctx.app.chats[id_] = ChatManager(
            ctx.app, id_, [req['user']],
            think=req.get('think', False), files=req.get('files'),
            search=req.get('search', False), email=req.get('email', False)
        )


@chisel.action(name='sendEmail', types=OLLAMA_CHAT_TYPES)
def send_email_request(ctx, req):
    with ctx.app.config() as config:
        conversation = config_conversation(config, req['id'])
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')
        exchange = conversation['exchanges'][-1]
        draft = exchange.get('email')
        if not draft:
            raise chisel.ActionError('NoEmailDraft')
        to, subject, body = draft['to'], draft['subject'], draft['body']

    # Discard the draft without sending?
    if not req.get('send', True):
        with ctx.app.config(save=True) as config:
            conversation = config_conversation(config, req['id'])
            if conversation and conversation['exchanges']:
                exchange = conversation['exchanges'][-1]
                email_draft = exchange.get('email')
                if email_draft and email_draft.get('to') == to:
                    del exchange['email']
        return {'sent': False}

    # Send the email, outside the config lock, and mark the draft as sent
    try:
        smtp_send_email(to, subject, body)
    except ValueError as exc:
        raise chisel.ActionError('SendFailed', str(exc)) from None
    with ctx.app.config(save=True) as config:
        conversation = config_conversation(config, req['id'])
        if conversation and conversation['exchanges']:
            exchange = conversation['exchanges'][-1]
            email_draft = exchange.get('email')
            if email_draft and email_draft.get('to') == to:
                email_draft['sent'] = True
    return {'sent': True}


@chisel.action(name='setConversationTitle', types=OLLAMA_CHAT_TYPES)
def set_conversation_title(ctx, req):
    with ctx.app.config(save=True) as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Busy?
        if id_ in ctx.app.chats:
            raise chisel.ActionError('ConversationBusy')

        # Set the conversation title
        conversation['title'] = req['title']


@chisel.action(name='deleteConversation', types=OLLAMA_CHAT_TYPES)
def delete_conversation(ctx, req):
    with ctx.app.config(save=True) as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Busy?
        if id_ in ctx.app.chats:
            raise chisel.ActionError('ConversationBusy')

        # Delete the conversation
        config['conversations'] = [conversation for conversation in config['conversations'] if conversation['id'] != id_]


@chisel.action(name='createTemplate', types=OLLAMA_CHAT_TYPES)
def create_template(ctx, req):
    with ctx.app.config(save=True) as config:
        # Create the new template
        id_ = str(uuid.uuid4())
        template = {
            'id': id_,
            'title': req['title'],
            'prompts': req['prompts']
        }
        if 'name' in req:
            template['name'] = req['name']
        if 'variables' in req:
            template['variables'] = req['variables']

        # Add the new template to the application config
        if 'templates' not in config:
            config['templates'] = []
        config['templates'].insert(0, template)

        # Return the new template identifier
        return {'id': id_}


@chisel.action(name='deleteConversationExchange', types=OLLAMA_CHAT_TYPES)
def delete_conversation_exchange(ctx, req):
    with ctx.app.config(save=True) as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Busy?
        if id_ in ctx.app.chats:
            raise chisel.ActionError('ConversationBusy')

        # Delete the most recent exchange
        exchanges = conversation['exchanges']
        if len(exchanges):
            del exchanges[-1]


@chisel.action(name='regenerateConversationExchange', types=OLLAMA_CHAT_TYPES)
def regenerate_conversation_exchange(ctx, req):
    with ctx.app.config(save=True) as config:
        id_ = req['id']
        conversation = config_conversation(config, id_)
        if conversation is None:
            raise chisel.ActionError('UnknownConversationID')

        # Busy?
        if id_ in ctx.app.chats:
            raise chisel.ActionError('ConversationBusy')

        # Any exchanges?
        exchanges = conversation['exchanges']
        if len(exchanges):
            # Delete the most recent exchange
            prompt = exchanges[-1]['user']
            del exchanges[-1]

            # Start the model chat
            ctx.app.chats[id_] = ChatManager(ctx.app, id_, [prompt])


@chisel.action(name='getModels', types=OLLAMA_CHAT_TYPES)
def get_models(ctx, unused_req):
    # Get the Ollama models
    models = ollama_list(ctx.app.pool_manager)

    # Create the models response
    response_models = [
        {
            'id': model['model'],
            'name': model['model'].split(':')[0],
            'parameters': _parse_parameter_size(ctx, model['details']['parameter_size']),
            'size': model['size'],
            'modified': model['modified_at']
        }
        for model in models
    ]

    with ctx.app.config() as config:
        # Create the downloading models response
        downloading_models = []
        for model_id, download_manager in ctx.app.downloads.items():
            download = {
                'id': model_id,
                'status': download_manager.status,
                'completed': download_manager.completed
            }
            if download_manager.total:
                download['size'] = download_manager.total
            downloading_models.append(download)

        response = {
            'models': sorted(response_models, key=lambda model: model['id']),
            'downloading': sorted(downloading_models, key=lambda model: model['id'])
        }
        if 'model' in config:
            response['model'] = config['model']
        if ctx.app.download_error:
            response['downloadError'] = ctx.app.download_error
            ctx.app.download_error = None
        return response


def _parse_parameter_size(ctx, parameter_size):
    # MLX models report an empty parameter size - return 0 without warning
    if parameter_size == '':
        return 0

    try:
        value = float(parameter_size[:-1])
        unit = parameter_size[-1].upper()
        if unit == 'T':
            return int(value * 1000000000000)
        elif unit == 'B':
            return int(value * 1000000000)
        elif unit == 'M':
            return int(value * 1000000)
        elif unit == 'K':
            return int(value * 1000)
    except (ValueError, IndexError):
        pass

    ctx.log.warning(f'Invalid parameter size "{parameter_size}"')
    return 0


@chisel.action(name='downloadModel', types=OLLAMA_CHAT_TYPES)
def download_model(ctx, req):
    with ctx.app.config():
        model = req['model']
        if model not in ctx.app.downloads:
            ctx.app.downloads[model] = DownloadManager(ctx.app, model)


@chisel.action(name='stopModelDownload', types=OLLAMA_CHAT_TYPES)
def stop_model_download(ctx, req):
    with ctx.app.config():
        if req['model'] in ctx.app.downloads:
            ctx.app.downloads[req['model']].stop = True


@chisel.action(name='deleteModel', types=OLLAMA_CHAT_TYPES)
def delete_model(ctx, req):
    ollama_delete(ctx.app.pool_manager, req['model'])


@chisel.action(name='getSystemInfo', types=OLLAMA_CHAT_TYPES)
def get_system_info(unused_ctx, unused_req):
    # Compute the total memory
    if platform.system() == "Windows": # pragma: no cover
        memory_status = MEMORYSTATUSEX()
        # pylint: disable-next=invalid-name, attribute-defined-outside-init
        memory_status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
        total_memory = memory_status.ullTotalPhys
    else: # pragma: no cover
        phys_pages = os.sysconf("SC_PHYS_PAGES") # pylint: disable=no-member,useless-suppression
        page_size = os.sysconf("SC_PAGE_SIZE") # pylint: disable=no-member,useless-suppression
        # os.sysconf returns -1 for an indeterminate value; report -1 (memory unknown) in that case
        total_memory = phys_pages * page_size if phys_pages > 0 and page_size > 0 else -1

    return {
        'memory': total_memory,
        'mlx': platform.system() == 'Darwin' and platform.machine() == 'arm64'
    }


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_uint),
        ("dwMemoryLoad", ctypes.c_uint),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]
