# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The built-in provider definitions - the seed list and the built-in providers' default base
URLs. Kept in its own module so provider adapters can use the defaults without importing the
registry (which imports the adapters).
"""


# The built-in providers, seeded into the config on first use. Base URLs are the documented
# defaults at seed time - they are editable, so they may have changed since. The Ollama entry
# has no base URL: the host comes from the OLLAMA_HOST environment variable (or the default)
# unless the user sets one.
DEFAULT_PROVIDERS = [
    {'id': 'ollama', 'name': 'Ollama', 'type': 'ollama'},
    {'id': 'openai', 'name': 'OpenAI', 'type': 'openai', 'baseUrl': 'https://api.openai.com/v1'},
    {'id': 'anthropic', 'name': 'Anthropic', 'type': 'anthropic', 'baseUrl': 'https://api.anthropic.com/v1'},
    {
        'id': 'google', 'name': 'Google (Gemini)', 'type': 'google',
        'baseUrl': 'https://generativelanguage.googleapis.com/v1beta'
    },
    {'id': 'mistral', 'name': 'Mistral', 'type': 'openai', 'baseUrl': 'https://api.mistral.ai/v1'},
    {'id': 'groq', 'name': 'Groq', 'type': 'openai', 'baseUrl': 'https://api.groq.com/openai/v1'},
    {'id': 'deepseek', 'name': 'DeepSeek', 'type': 'openai', 'baseUrl': 'https://api.deepseek.com'},
    {'id': 'openrouter', 'name': 'OpenRouter', 'type': 'openai', 'baseUrl': 'https://openrouter.ai/api/v1'},
    {'id': 'opencode', 'name': 'OpenCode', 'type': 'openai', 'baseUrl': 'https://opencode.ai/zen/v1'}
]


# A provider's effective base URL - the entry's URL, or the built-in provider's seed default
def provider_base_url(provider):
    default = next((default for default in DEFAULT_PROVIDERS if default['id'] == provider.get('id')), None)
    return provider.get('baseUrl') or (default or {}).get('baseUrl')
