# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The AI provider abstraction. A provider adapts a chat back-end (local Ollama, an
OpenAI-compatible server, Anthropic, Google, ...) to the chat manager's single internal
message format - the Ollama chat API's message and streamed-chunk format. Conversion to and
from a specific provider's API format happens inside the adapter; the chat code never sees a
provider-specific format.
"""


# A provider error with a user-facing message. "code" is a stable, machine-readable identifier
# (e.g. "InvalidApiKey", "RateLimited", "UnknownModel"); "message" is safe to display in the
# chat - it never includes the API key, the provider request, or a raw traceback.
class ProviderError(Exception):
    __slots__ = ('code', 'message')


    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# A chat provider adapter. Messages in and streamed chunks out use the internal format - the
# Ollama chat API format:
#
# - request messages: {'role': 'user'|'assistant'|'system'|'tool', 'content': str,
#   optional 'images': [base64 str], optional 'tool_calls': [...], optional 'tool_name': str}
# - streamed chunks: {'message': optional {'content'?: str, 'thinking'?: str,
#   'tool_calls'?: [...]}, optional 'done': bool}
class Provider:
    __slots__ = ('pool_manager', 'config', 'crypto')


    # Provider-level capability defaults, applied to every model of the provider unless the
    # adapter can detect per-model capabilities
    supports_tools = False
    supports_vision = False
    supports_thinking = False


    def __init__(self, pool_manager, config=None, crypto=None):
        self.pool_manager = pool_manager
        self.config = config or {}
        self.crypto = crypto


    # The provider's available models, as dicts {'id': str, 'name': str}
    def list_models(self):
        raise NotImplementedError


    # A model's capabilities - {'tools': bool, 'vision': bool, 'thinking': bool}
    def model_capabilities(self, model):  # pylint: disable=unused-argument
        return {
            'tools': self.supports_tools,
            'vision': self.supports_vision,
            'thinking': self.supports_thinking
        }


    # Stream a chat response, yielding internal-format chunks. "think" enables thinking mode
    # (None means the provider's default behavior), "tools" offers tool definitions, "num_ctx"
    # is a context-size option (ignored by providers without such an option), and
    # "capabilities" may carry a previously fetched model_capabilities() result so the adapter
    # doesn't need a duplicate metadata request.
    def chat_stream(self, model, messages, think=None, tools=None, num_ctx=None, capabilities=None):
        raise NotImplementedError


    # Check the provider's connection (and its API key, where applicable). Returns a short,
    # human-readable summary string; raises ProviderError on failure.
    def test_connection(self):
        raise NotImplementedError
