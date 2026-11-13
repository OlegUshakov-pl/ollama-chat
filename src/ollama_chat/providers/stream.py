# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
Shared streaming helpers for provider HTTP responses. These were originally written for the
Ollama chat API's NDJSON streaming and are reused by the provider adapters, which stream
newline-delimited JSON (Ollama) or server-sent events (OpenAI-compatible, Anthropic, Google).
"""

import codecs
import json
import queue
import threading

import urllib3


# The maximum number of seconds without a streamed chunk before the stream is considered stalled -
# a broken model template can crash Ollama's llama-server mid-stream, leaving the connection open
# but silent (the chat would hang forever without this watchdog)
STREAM_IDLE_TIMEOUT = 240.0

_QUEUE_CLOSED_CHUNK = object()

# Capture the real thread class at import time - unit tests globally patch "threading.Thread" to
# prevent background threads, but the watchdog reader must always run
ThreadClass = threading.Thread


# Decode a streamed, newline-delimited JSON (NDJSON) response into individual JSON objects. The
# Ollama API streams one JSON object per line, but HTTP chunk boundaries do not align with those
# lines - a single chunk may carry multiple objects (common with cloud models) or a partial object
# split across chunks. Buffer the decoded text and yield each complete JSON object as it arrives.
def iter_ndjson(response):
    decoder = json.JSONDecoder()
    text_decoder = codecs.getincrementaldecoder('utf-8')()
    buffer = ''
    for data in watch_chunks(response.read_chunked()):
        buffer += text_decoder.decode(data)
        while True:
            buffer = buffer.lstrip()
            if not buffer:
                break
            try:
                chunk, index = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                # Incomplete object - wait for the next chunk to complete it
                break
            buffer = buffer[index:]
            yield chunk

    # The stream ended mid-object - the response was truncated or malformed
    if buffer.strip():
        raise urllib3.exceptions.HTTPError(f'Invalid streamed response: {buffer.strip()!r}')


# Read the streamed HTTP chunks from a reader thread, raising if no chunk arrives within
# "timeout" seconds (the watchdog thread itself never blocks the reader)
def watch_chunks(raw_chunks, timeout=None):
    timeout = STREAM_IDLE_TIMEOUT if timeout is None else timeout
    chunk_queue = queue.Queue()
    raised = None

    def _read_chunks():
        nonlocal raised
        try:
            for raw_chunk in raw_chunks:
                chunk_queue.put(raw_chunk)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            raised = exc
        chunk_queue.put(_QUEUE_CLOSED_CHUNK)

    reader_thread = ThreadClass(target=_read_chunks, daemon=True)
    reader_thread.start()
    while True:
        try:
            chunk = chunk_queue.get(timeout=timeout)
        except queue.Empty:
            raise urllib3.exceptions.HTTPError( \
                f'Stream stalled - no data for {timeout:.0f} seconds' \
            ) from None
        if chunk is _QUEUE_CLOSED_CHUNK:
            if raised is not None:
                raise raised
            return
        yield chunk


# Iterate a server-sent events (SSE) stream, yielding the JSON payload of each "data:" line.
# The OpenAI-compatible, Anthropic and Google streaming APIs all use the SSE framing - event
# boundaries do not align with HTTP chunk boundaries, so the bytes are buffered and split on
# newlines. Non-"data:" lines (comments, "event:", empty keep-alives) are ignored.
def iter_sse_json(response):
    text_decoder = codecs.getincrementaldecoder('utf-8')()
    buffer = ''
    for data in watch_chunks(response.read_chunked()):
        buffer += text_decoder.decode(data)
        while True:
            newline_index = buffer.find('\n')
            if newline_index < 0:
                break
            line = buffer[:newline_index].rstrip('\r')
            buffer = buffer[newline_index + 1:]
            if not line.startswith('data:'):
                continue
            payload = line[len('data:'):].strip()
            if not payload or payload == '[DONE]':
                continue
            yield json.loads(payload)
