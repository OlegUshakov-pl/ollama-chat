# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import datetime
import os

import urllib3

from .providers.stream import iter_ndjson as _iter_ndjson, watch_chunks as _watch_chunks


# Helper function to get an Ollama API URL. The base URL comes from the provider's config, or
# the OLLAMA_HOST environment variable.
def _get_ollama_url(path, base_url=None):
    ollama_host = base_url or os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    return f'{ollama_host}{path}'


# Extract Ollama's error message from an error response body, for display in the UI
def _error_detail(response):
    try:
        body = response.json()
    except (ValueError, AttributeError):
        return ''
    if isinstance(body, dict):
        error = body.get('error')
        if isinstance(error, str):
            return error
        if isinstance(error, dict):
            return str(error.get('message') or '')
    return ''


# Get an Ollama model's metadata (including its capabilities)
def ollama_show(pool_manager, model, base_url=None):
    url_show = _get_ollama_url('/api/show', base_url)
    data_show = {'model': model}
    response_show = pool_manager.request('POST', url_show, json=data_show, retries=0)
    try:
        if response_show.status != 200:
            error_detail = _error_detail(response_show)
            raise urllib3.exceptions.HTTPError( \
                f'Unknown model "{model}" ({response_show.status})' + \
                (f': {error_detail}' if error_detail else '') \
            )
        return response_show.json()
    finally:
        response_show.close()


# Call the Ollama chat API and yield each streamed JSON response chunk
def ollama_chat(pool_manager, model, messages, think=None, tools=None, model_show=None, num_ctx=None, base_url=None):
    # Is this a thinking model?
    if model_show is None:
        model_show = ollama_show(pool_manager, model, base_url)
    is_thinking = think if think is not None else ('capabilities' in model_show and 'thinking' in model_show['capabilities'])

    # Start a streaming chat request
    url_chat = _get_ollama_url('/api/chat', base_url)
    data_chat = {'model': model, 'messages': messages, 'stream': True, 'think': is_thinking}
    if tools:
        data_chat['tools'] = tools
    if num_ctx is not None:
        data_chat['options'] = {'num_ctx': num_ctx}
    response_chat = pool_manager.request('POST', url_chat, json=data_chat, preload_content=False, retries=0)
    try:
        if response_chat.status != 200:
            error_detail = _error_detail(response_chat)
            raise urllib3.exceptions.HTTPError( \
                f'Unknown model "{model}" ({response_chat.status})' + \
                (f': {error_detail}' if error_detail else '') \
            )

        # Respond with each streamed JSON chunk
        for chunk in _iter_ndjson(response_chat):
            if 'error' in chunk:
                raise urllib3.exceptions.HTTPError(chunk['error'])
            yield chunk
    finally:
        response_chat.close()


# List the locally available Ollama models
def ollama_list(pool_manager, base_url=None):
    url_list = _get_ollama_url('/api/tags', base_url)
    response_list = pool_manager.request('GET', url_list, retries=0)
    try:
        if response_list.status != 200:
            raise urllib3.exceptions.HTTPError(f'Unexpected error ({response_list.status})')
        return [
            {
                'model': model['model'],
                'details': model['details'],
                'size': model['size'],
                'modified_at': datetime.datetime.fromisoformat(model['modified_at'])
            }
            for model in response_list.json()['models']
        ]
    finally:
        response_list.close()


# Delete a locally available Ollama model
def ollama_delete(pool_manager, model, base_url=None):
    url_delete = _get_ollama_url('/api/delete', base_url)
    data_delete = {'model': model}
    response_delete = pool_manager.request('DELETE', url_delete, json=data_delete, retries=0)
    try:
        if response_delete.status != 200:
            raise urllib3.exceptions.HTTPError(f'Unknown model "{model}" ({response_delete.status})')
    finally:
        response_delete.close()


# Pull an Ollama model, yielding each streamed JSON progress chunk
def ollama_pull(pool_manager, model, base_url=None):
    url_pull = _get_ollama_url('/api/pull', base_url)
    data_pull = {'model': model, 'stream': True}
    response_pull = pool_manager.request('POST', url_pull, json=data_pull, preload_content=False, retries=0)
    try:
        if response_pull.status != 200:
            raise urllib3.exceptions.HTTPError(f'Unknown model "{model}" ({response_pull.status})')

        # Respond with each streamed JSON chunk
        for chunk in _iter_ndjson(response_pull):
            if 'error' in chunk:
                raise urllib3.exceptions.HTTPError(chunk['error'])
            yield chunk
    finally:
        response_pull.close()
