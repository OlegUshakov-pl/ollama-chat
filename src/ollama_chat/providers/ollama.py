# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The Ollama provider adapter - the local Ollama chat API wrapped as a Provider. The chat
manager used to call the ollama module directly; this adapter is that logic, unchanged. The
base URL comes from the provider's config entry, or the OLLAMA_HOST environment variable when
there is none.
"""

from ..ollama import ollama_chat, ollama_list, ollama_show
from .base import Provider


# The Ollama provider. Model capabilities come from Ollama's /api/show metadata.
class OllamaProvider(Provider):
    __slots__ = ()


    def list_models(self):
        return [
            {'id': model['model'], 'name': model['model']}
            for model in ollama_list(self.pool_manager, self.config.get('baseUrl'))
        ]


    def model_capabilities(self, model):
        try:
            model_show = ollama_show(self.pool_manager, model, self.config.get('baseUrl'))
        except Exception:  # pylint: disable=broad-exception-caught
            return {'tools': False, 'vision': False, 'thinking': False}
        capabilities = model_show.get('capabilities') or []
        return {
            'tools': 'tools' in capabilities,
            'vision': 'vision' in capabilities,
            'thinking': 'thinking' in capabilities
        }


    def chat_stream(self, model, messages, think=None, tools=None, num_ctx=None, capabilities=None):
        # Reuse a previously fetched capabilities result - without one, ollama_chat fetches
        # the model metadata itself (one /api/show request per turn, as before)
        base_url = self.config.get('baseUrl')
        model_show = None
        if capabilities is not None:
            model_show = {'capabilities': [name for name, has in capabilities.items() if has]}
        yield from ollama_chat( \
            self.pool_manager, model, messages, \
            think=think, tools=tools, model_show=model_show, num_ctx=num_ctx, base_url=base_url \
        )


    def test_connection(self):
        models = self.list_models()
        return f'Ollama is available ({len(models)} models)'
