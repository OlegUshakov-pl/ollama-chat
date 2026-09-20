![ollama-chat](assets/image.png)

# ollama-chat

[![PyPI - Status](https://img.shields.io/pypi/status/ollama-chat)](https://pypi.org/project/ollama-chat/)
[![PyPI](https://img.shields.io/pypi/v/ollama-chat)](https://pypi.org/project/ollama-chat/)
[![GitHub](https://img.shields.io/github/license/craigahobbs/ollama-chat)](https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ollama-chat)](https://pypi.org/project/ollama-chat/)

**Ollama Chat** is a conversational AI chat client that uses [Ollama](https://ollama.com) to interact with local large language models (LLMs) entirely offline. Ideal for AI enthusiasts, developers, or anyone wanting private, offline LLM chats.

> **Fork:** [OlegUshakov-pl/ollama-chat](https://github.com/OlegUshakov-pl/ollama-chat) — fork of [craigahobbs/ollama-chat](https://github.com/craigahobbs/ollama-chat) with a redesigned theme, thinking-mode toggle, and file attachments.

## What's new in this fork

- **Completely redesigned theme** — light and dark modes (`prefers-color-scheme` + `data-theme`), new layout for sidebar / composer / messages, mobile-responsive. See `src/ollama_chat/static/app.css:1` (983 lines), screenshot above.
- **Thinking mode toggle** — paw-icon button in the composer. Enables/disables `think` for `/api/chat`. State is persisted in `localStorage` (`ollama-chat-thinking`) and sent as `{"think": true|false}` via `startConversation` / `replyConversation` / `startTemplate` → `ChatManager(think=...)` → `ollama_chat(..., think=...)` (`src/ollama_chat/ollama.py:43`, `src/ollama_chat/chat.py:23`, `src/ollama_chat/app.py:320`). For reasoning models you can force thinking on or off; for other models leave it off. Visual active state is `icon-btn thinking-active` (`src/ollama_chat/static/app.css:777`, `src/ollama_chat/static/app.js:48`).
- **File attachments for the model** — upload button in the composer (hidden `<input type="file">`). Supported types: `txt`, `md`, `docx`, `png`, `jpg`, `jpeg`. Text files are appended to the last `user` message, `docx` is parsed with `python-docx` (`pyproject.toml:34`), images are sent as base64 in `images` (`src/ollama_chat/chat.py:64`, `src/ollama_chat/static/app.js:111`). Selected file names are shown as a `file-pill`; you can send with files even when the text input is empty.
- **One-click Windows launch — `start.bat` / `install.bat`** — clone and run locally without manual venv setup. `install.bat:1` clones the repo into a clean folder and installs `.venv` + dependencies; `start.bat:1` creates `.venv` if needed and starts the server. All arguments are forwarded to `ollama-chat` (e.g. `start.bat -p 8080`).

## Quick start

Requirements: [Ollama](https://ollama.com/download) running + Python 3.11+ and Git on `PATH`.

### Option A — via `install.bat` (clean folder, recommended for Windows)

The easiest way for new users — just copy `install.bat` into an empty folder and run it:

1. Create an empty folder and copy `install.bat` from this repository into it (or [download it](https://github.com/OlegUshakov-pl/ollama-chat/raw/main/install.bat)).
2. Double-click `install.bat` (or run `install.bat` from a console).

   `install.bat:1` will clone `https://github.com/OlegUshakov-pl/ollama-chat.git` into `.\ollama-chat` (if not already present), create `.venv`, upgrade `pip`, and run `pip install -e .` (includes `python-docx` for `.docx` support).

3. Go to the cloned folder and start the server:

   ```bat
   cd ollama-chat
   start.bat
   ```

   The app opens at http://127.0.0.1:8080/ , config file is `ollama-chat.json` in the user's home directory.

### Option B — via `start.bat` (if you already cloned)

```bat
git clone https://github.com/OlegUshakov-pl/ollama-chat.git
cd ollama-chat
start.bat
```

What `start.bat` does (`start.bat:1`):
1. Creates `.venv` in the project root if missing (`python -m venv .venv`).
2. Activates the environment and removes stale `~*` directories from `site-packages`.
3. Installs dependencies and the package (`pip install -e .`) if `.venv\Scripts\ollama-chat.exe` is not yet present (skips on re-run, works offline).
4. Runs `ollama-chat %*` — all arguments are forwarded (e.g. `start.bat -p 8080 -h 127.0.0.1`).

You can also double-click `start.bat` in File Explorer.

> If `OLLAMA_HOST` is not `http://127.0.0.1:11434`, set the environment variable before launching — see `src/ollama_chat/ollama.py:19`.

## Manual installation

**macOS and Linux**

```sh
python3 -m venv $HOME/venv --upgrade-deps
. $HOME/venv/bin/activate
pip install -e .   # or pip install ollama-chat for the upstream
ollama-chat
```

**Windows (without `start.bat`)**

```bat
python -m venv %USERPROFILE%\venv --upgrade-deps
%USERPROFILE%\venv\Scripts\activate
pip install -e .
ollama-chat
```

The app opens at http://127.0.0.1:8080/. Start a conversation or template from the CLI:

```sh
ollama-chat -m "Why is the sky blue?"
ollama-chat -t askAristotle -v question "Why is the sky blue?"
```

## Features

- Chat with local LLMs entirely offline, multiple concurrent chats
- **Thinking toggle** — paw button in the composer (`thinkingOn`/`thinkingOff`, `src/ollama_chat/static/app.js:48`), respects model `capabilities` fallback (`src/ollama_chat/ollama.py:57`)
- **File uploads** — `txt`/`md`/`docx` as text, `png`/`jpg`/`jpeg` as images; pill with file names, sending with empty text allowed
- Prompt commands `/file`, `/dir`, `/image`, `/url`, `/do`, `/?` (see below)
- Conversation templates with `{{var}}` substitution
- Browse, download, monitor, and select local models directly in the app, streaming responses
- Show/hide thinking for reasoning models, regenerate/delete most recent exchange, Markdown/text view, save as Markdown
- Light and dark themes, responsive layout

## Usage

### Thinking mode

Button to the left of the upload button in the composer. Active state is `icon-btn thinking-active` (`src/ollama_chat/static/app.css:777`). The state persists across restarts. On send it is included as `{"think": true|false}` in the API request — the backend honors an explicit value and otherwise falls back to model capabilities (`src/ollama_chat/ollama.py:57`).

### File attachments

Click the upload icon, select files (`accept=".txt,.md,.docx,.png,.jpg,.jpeg"`), names appear as a pill. On send, files are read with `FileReader` as text/base64 (`src/ollama_chat/static/app.js:111`) and attached on the server (`src/ollama_chat/chat.py:65`). No frontend size limit — limited by the model/Ollama.

## Prompt commands

Same as upstream (implemented in `src/ollama_chat/chat.py`):

- `/file` - include a file

  ```
  /file README.md
  ```

- `/image` - include an image

  ```
  /image image.jpeg
  ```

- `/dir` - include files from a directory

  ```
  /dir src/ollama_chat py
  ```

- `/url` - include a URL resource

  ```
  /url https://craigahobbs.github.io/ollama-chat/README.md
  ```

- `/do` - execute a conversation template by name

  ```
  /do city-report -v CityState "Seattle, WA"
  ```

- `/?` - list available prompt commands

  ```
  /?
  ```

To get prompt command help use the `-h` option:

```
 /file -h
```

## Conversation templates

Conversation Templates allow you to repeat a sequence of prompts. Templates can include variable substitutions in the title text and the prompt text (e.g., `{{var}}`).

### Create a Template

- Click "Add Template" from the home page
- Click "Template" on a conversation page

### Run a Template

Click its title on the home page. If the template has variables, you are prompted for values before a new conversation is created and prompts are entered in sequence.

### Edit a Template

From the home page, click "Select" on the template, then "Edit" to update title, name, variables, and prompts.

## Add a desktop launcher

### macOS

In Finder, locate the `ollama-chat` executable and drag-and-drop it into the lower portion of the Dock.

### Windows

In File Explorer, locate the `ollama-chat` executable, right-click it, and select "Pin to Start". For the fork, you can also pin `start.bat`.

### GNOME (Linux)

1. Copy the following desktop file contents:

   ```
   [Desktop Entry]
   Name=Ollama Chat
   Exec=sh -c "$HOME/venv/bin/ollama-chat"
   Type=Application
   Icon=dialog-information
   Terminal=true
   Categories=Utility;
   ```

2. Create the desktop file and paste the contents:

   ```
   nano $HOME/.local/share/applications/ollama-chat.desktop
   ```

3. Update the `Exec` path, if necessary, and save

## File format and API documentation

[Ollama Chat File Format](https://craigahobbs.github.io/ollama-chat/api.html#var.vName='OllamaChatConfig')

[Ollama Chat API](https://craigahobbs.github.io/ollama-chat/api.html)

Schema is in `src/ollama_chat/static/ollamaChat.smd` — this fork adds `think`/`files` fields to `StartConversation`/`ReplyConversation`/`StartTemplate`.

## Development

This package is developed using [python-build](https://github.com/craigahobbs/python-build#readme). It was started using [python-template](https://github.com/craigahobbs/python-template#readme) as follows:

```
template-specialize python-template/template/ ollama-chat/ -k package ollama-chat -k name 'Craig A. Hobbs' -k email 'craigahobbs@gmail.com' -k github 'craigahobbs' -k noapi 1
```

```sh
make test        # backend tests (urllib3 is mocked, no live Ollama required)
make test-app    # BareScript frontend tests (TEST="exact test name")
make lint        # also runs pylint on static/models/models.py
make run ARGS='...'  # start the app from the default venv
```

Upstream: https://github.com/craigahobbs/ollama-chat · Fork: https://github.com/OlegUshakov-pl/ollama-chat
