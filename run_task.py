#!/usr/bin/env python3
# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
Run an ollama-chat scheduled task outside the chat application. Intended for the
Windows Task Scheduler (or any cron-like scheduler).

Example usage:

    python run_task.py briefing
"""

import argparse
import json
import os
import sys

# Import the ollama-chat package from this repository, when running from a repo checkout
_repo_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if os.path.isdir(_repo_src):
    sys.path.insert(0, _repo_src)

import urllib3  # noqa: E402

from ollama_chat.memory import workspace_dir  # noqa: E402
from ollama_chat.tasks import run_stored_task  # noqa: E402


# The default config file name
CONFIG_FILENAME = 'ollama-chat.json'


def main(argv=None):
    # Windows console encodings (e.g. cp1250) can't encode model output - use UTF-8 with
    # replacement, more useful than a UnicodeEncodeError crash
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    # Command line arguments
    parser = argparse.ArgumentParser(prog='run_task')
    parser.add_argument('id', help='the scheduled task ID')
    parser.add_argument('-c', metavar='FILE', dest='config', help= \
        'the configuration file (default is "$HOME/ollama-chat.json")' \
    )
    args = parser.parse_args(args=argv)

    # Load the config file, like the application does
    config_path = args.config
    if config_path is None:
        if os.path.isfile(CONFIG_FILENAME):
            config_path = CONFIG_FILENAME
        else:
            config_path = os.path.join(os.path.expanduser('~'), CONFIG_FILENAME)
    elif config_path.endswith(os.sep) or os.path.isdir(config_path):
        config_path = os.path.join(config_path, CONFIG_FILENAME)
    try:
        with open(config_path, 'r', encoding='utf-8') as config_fh:
            config = json.load(config_fh)
    except (OSError, ValueError) as exc:
        print(f'run_task: failed to load config "{config_path}": {exc}', file=sys.stderr)
        return 1

    # Run the task
    workspace = str(workspace_dir(config))
    pool_manager = urllib3.PoolManager(num_pools=10, maxsize=10)
    try:
        from ollama_chat.app import OllamaChat  # noqa: E402
        app = OllamaChat(config_path)
        pool_manager.app = app
        pool_manager.crypto = app.crypto
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        report = run_stored_task(workspace, pool_manager, args.id)
    except ValueError as exc:
        print(f'run_task: {exc}', file=sys.stderr)
        return 1

    # Report the result
    if report is None:
        print(f'run_task: task "{args.id}" failed - see {workspace}/logs', file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
