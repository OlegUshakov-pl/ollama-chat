# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The provider registry - the built-in providers and creating a provider adapter from a
provider config entry.
"""


from .anthropic import AnthropicProvider
from .base import ProviderError
from .defaults import DEFAULT_PROVIDERS
from .google import GoogleProvider
from .ollama import OllamaProvider
from .openai_compat import OpenAICompatProvider


# The provider used when a conversation or task doesn't specify one - local Ollama
DEFAULT_PROVIDER_ID = 'ollama'

# The API types an OpenAI-compatible adapter serves. These providers differ only in their
# base URL and API key - "custom" covers any user-added OpenAI-compatible server.
OPENAI_COMPATIBLE_TYPES = ('openai', 'custom')


# The provider adapter classes, by provider API type
_PROVIDER_CLASSES = {
    'ollama': OllamaProvider,
    'openai': OpenAICompatProvider,
    'custom': OpenAICompatProvider,
    'anthropic': AnthropicProvider,
    'google': GoogleProvider
}


# Find a provider's config entry in the app config, or None
def find_provider_config(app_config, provider_id):
    return next( \
        (provider for provider in (app_config.get('providers') or []) if provider.get('id') == provider_id), \
        None \
    )


# A provider's config entry, falling back to the built-in defaults when the config has no
# entry for it (e.g. before the settings page seeded the providers). Returns None for an
# unknown provider ID.
def provider_config(app_config, provider_id):
    entry = find_provider_config(app_config, provider_id)
    if entry is not None:
        return entry
    default = next((default for default in DEFAULT_PROVIDERS if default['id'] == provider_id), None)
    return dict(default) if default is not None else None


# Create a provider adapter for a provider ID (a conversation's or task's "provider" value).
# "config" is the provider's config dict entry, or None when the provider isn't configured -
# built-in defaults are used. "crypto" decrypts the entry's stored API key. Raises
# ProviderError for an unknown provider ID.
def create_provider(provider_id, pool_manager, config=None, crypto=None):
    entry = config or {}
    provider_class = _PROVIDER_CLASSES.get(entry.get('type') or (provider_id or DEFAULT_PROVIDER_ID))
    if provider_class is None:
        raise ProviderError('UnknownProvider', f'Unknown provider "{provider_id}"')
    return provider_class(pool_manager, entry, crypto=crypto)
