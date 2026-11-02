![ollama-chat](assets/image.png)

# ollama-chat

[![PyPI](https://img.shields.io/pypi/v/ollama-chat)](https://pypi.org/project/ollama-chat/)
[![GitHub](https://img.shields.io/github/license/craigahobbs/ollama-chat)](https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ollama-chat)](https://pypi.org/project/ollama-chat/)

**Ollama Chat** is a conversational AI chat client that uses [Ollama](https://ollama.com) to interact with local large language models (LLMs) entirely offline. Private, fast, no cloud.

> **Fork:** [OlegUshakov-pl/ollama-chat](https://github.com/OlegUshakov-pl/ollama-chat) — fork of [craigahobbs/ollama-chat](https://github.com/craigahobbs/ollama-chat) with a redesigned UI, thinking mode, web search, file attachments, scheduled tasks, PDF export and dedicated Settings / Tasks pages.

## Quick start

Requirements: [Ollama](https://ollama.com/download) running + Python 3.11+ and Git on `PATH`.

**Windows:**
```bat
git clone https://github.com/OlegUshakov-pl/ollama-chat.git
cd ollama-chat
start.bat
```
(`install.bat` installs into an empty folder without cloning manually.)

**macOS / Linux:**
```sh
python3 -m venv $HOME/venv --upgrade-deps
. $HOME/venv/bin/activate
pip install -e .
ollama-chat
```

The app opens at http://127.0.0.1:8080/ — the server binds to `127.0.0.1` only, so it is not reachable from your network. Config is `ollama-chat.json` in the home directory.

## Features

- Offline chats with local LLMs, multiple concurrent conversations
- **Thinking toggle** and **web search toggle** (tool calling with SSRF protection)
- **File attachments** — up to 10 files per message (`txt`/`md`/`docx` as text, `png`/`jpg`/`jpeg` as images)
- **Markdown viewer** — open local `.md` files rendered safely in the chat area
- Prompt commands: `/file`, `/dir`, `/image`, `/url`, `/memory`, `/remember`, `/forget`, `/do`, `/?`
- **Settings page** (`#/settings`) — workspace folder and Gmail IMAP/SMTP settings with a connection test
- **Tasks page** (`#/tasks`) — scheduled prompts (like cron) with enable toggle, run log and "Run now"
- Conversation templates with `{{var}}` substitution; model browser with download and streaming
- Rename / Delete / Download `.md` / Export PDF per chat
- Light / dark themes, responsive layout

## Settings

The **Settings** page holds everything that used to live on the home page.

**Workspace** — the folder for long-term memory and data (`~/ollama-chat-workspace` by default, or set `OLLAMA_CHAT_WORKSPACE`):

```
<workspace>/memory/USER.md      # background information about the user
<workspace>/memory/MEMORY.md    # notes remembered across conversations
<workspace>/memory/daily/       # task reports and dated notes
<workspace>/.env                # email settings (see below)
<workspace>/tasks.json, logs/, exports/
```

The memory is injected into the system prompt for every model turn and managed in chat with `/memory`, `/remember <text>`, `/forget <phrase>`.

**Gmail (IMAP / SMTP)** — enables the email tools (`check_email` in chat, `check_email` / `send_email` in tasks). Fill in the IMAP/SMTP hosts and ports, your e-mail address and a Google **application password** — everything is written to `<workspace>/.env` (same format as `.env.example`).

The app password is write-only by design: it is never stored in `ollama-chat.json`, never committed to git (`.env` is in `.gitignore`) and never sent back to the browser — reopening the page shows the field empty with a `(saved)` placeholder; saving with an empty password keeps the saved one. **Test connection** logs in to both servers (no e-mail is sent).

## Scheduled tasks

Tasks run a prompt on a schedule without a conversation: they read the workspace memory, may use the tools, and append the report to `<workspace>/memory/daily/YYYY-MM-DD.md`. Errors go to `<workspace>/logs/YYYY-MM-DD.log`.

On the **Tasks** page: create/edit tasks (name, time, run days, prompt, model, context size, tools), toggle them on/off, run immediately, view the log or delete. `send_email` is opt-in (unchecked by default) since a task sending e-mail has no confirmation step.

Prompt commands also work:
```
/tasks
/task add "Morning briefing" -t 09:00 -d weekdays -m llama3.1 Make a briefing of my memory and the news about AI
/task run briefing
/task remove briefing
```

Tasks can also run outside the app via the Windows Task Scheduler with `run_task.py`:
```
python run_task.py briefing
```

## Development

- `make test` — backend tests (341, `urllib3` mocked)
- `make test-app` — BareScript frontend tests (141)
- `make lint` — pylint
- `make run ARGS='...'` — start the app from the default venv

API schema: `src/ollama_chat/static/ollamaChat.smd`. Upstream: https://github.com/craigahobbs/ollama-chat
