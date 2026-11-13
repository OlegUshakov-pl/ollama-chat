# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
Shared HTTP plumbing for the cloud provider adapters - the API URL, the API key, the
request with timeouts and retries, and the common HTTP-status-to-user-message mapping. Each
provider adapter subclasses this and adds its own request/response format conversion.
"""

import time
from urllib.parse import urlsplit

import urllib3

from .base import Provider, ProviderError
from .defaults import provider_base_url
from .stream import STREAM_IDLE_TIMEOUT


# The retry pauses for rate-limited (429) and server-error (5xx) responses
_RETRY_DELAYS = (1.0, 2.0)

# The maximum number of characters of a provider error message included in a user-facing error
_ERROR_DETAIL_MAX = 200


# A cloud chat provider over HTTP - the request/error handling shared by the OpenAI-compatible,
# Anthropic and Google adapters
class HTTPProvider(Provider):  # pylint: disable=abstract-method
    __slots__ = ()


    # The provider's display name, for user-facing error messages
    @property
    def provider_name(self):
        return self.config.get('name') or self.config.get('id') or 'provider'


    # A provider API URL, from the configured base URL (falling back to the built-in seed
    # default for a built-in provider)
    def _api_url(self, path):
        base_url = (provider_base_url(self.config) or '').rstrip('/')
        if not base_url:
            raise ProviderError(
                'BadBaseUrl',
                f'The provider "{self.provider_name}" has no base URL - set one in settings.'
            )
        return f'{base_url}/{path}'


    # The request headers carrying the API key. Overridden by providers with a different auth
    # scheme (e.g. Anthropic's x-api-key, Google's query parameter)
    def _base_headers(self):
        headers = {'Content-Type': 'application/json'}
        api_key = self._api_key()
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        return headers


    # Make a provider request with connection/read timeouts, retrying rate-limited and
    # server-error responses at most twice. Returns the (unclosed) response; raises
    # ProviderError for connection failures.
    def _request(self, method, url, body=None, headers=None):
        request_headers = self._base_headers()
        if headers:
            request_headers.update(headers)
        timeout = urllib3.Timeout(connect=10.0, read=STREAM_IDLE_TIMEOUT)
        attempt = 0
        while True:
            try:
                response = self.pool_manager.request(
                    method, url, json=body, headers=request_headers, preload_content=False,
                    retries=0, timeout=timeout
                )
            except (urllib3.exceptions.HTTPError, OSError) as exc:
                raise ProviderError(
                    'ConnectionFailed',
                    f'Could not connect to {self.provider_name} ({_url_host(url)}): {_error_text(exc)}'
                ) from None

            # Retry rate-limited and server-error responses
            if response.status == 429 or response.status >= 500:
                if attempt < len(_RETRY_DELAYS):
                    response.close()
                    time.sleep(_RETRY_DELAYS[attempt])
                    attempt += 1
                    continue
            return response


    # The decrypted API key, or '' when none is saved (keyless custom servers work; cloud
    # providers answer 401, which the error mapping explains)
    def _api_key(self):
        api_key_enc = self.config.get('apiKeyEnc')
        if not api_key_enc:
            return ''
        if self.crypto is None:
            raise ProviderError(
                'BadApiKey',
                f'The provider "{self.provider_name}" has a saved API key that cannot be read.'
            )
        try:
            return self.crypto.decrypt_api_key(api_key_enc)
        except ValueError as exc:
            raise ProviderError('BadApiKey', f'{self.provider_name}: {exc}') from None


    # Raise a ProviderError with a user-friendly message for a non-200 response. Never
    # includes the API key or the request body.
    def _raise_for_status(self, response, model=None):
        status = response.status
        detail = _error_detail_text(response)
        try:
            response.close()
        except Exception:
            pass
        detail_lower = detail.lower()
        if status in (401, 403) or (status == 400 and 'api key' in detail_lower):
            raise ProviderError(
                'InvalidApiKey',
                f'{self.provider_name} rejected the API key (HTTP {status}). '
                'Check the API key in settings.' + (f' - {detail}' if detail else '')
            )
        if status == 429:
            raise ProviderError(
                'RateLimited',
                f'{self.provider_name} rate limit reached (HTTP 429). Try again later.'
                + (f' - {detail}' if detail else '')
            )
        if status == 404:
            if model is not None and 'model' in detail_lower:
                raise ProviderError(
                    'UnknownModel',
                    f'The model "{model}" was not found on {self.provider_name}. '
                    'Refresh the model list and select another model.'
                )
            raise ProviderError(
                'BadBaseUrl',
                f'{self.provider_name} returned HTTP 404 - check the base URL in settings.'
                + (f' - {detail}' if detail else '')
            )
        if status >= 500:
            raise ProviderError(
                'ProviderUnavailable',
                f'{self.provider_name} is unavailable (HTTP {status}). Try again later.'
                + (f' - {detail}' if detail else '')
            )
        raise ProviderError(
            'ProviderError',
            f'{self.provider_name} returned HTTP {status}.' + (f' - {detail}' if detail else '')
        )


# Extract an error message text from a provider error payload (dict, list or string)
def _error_text(error):
    if isinstance(error, dict):
        detail = error.get('message') or error.get('detail') or error.get('code') or ''
        if isinstance(detail, dict):
            detail = detail.get('message') or ''
        return str(detail)
    return str(error)


# Read a JSON response body
def _response_json(response):
    try:
        return response.json()
    except ValueError:
        return {}


# Read an error response body's message text, truncated for display
def _error_detail_text(response):
    try:
        body = response.data
        detail = _error_text(response.json())
    except (ValueError, AttributeError, OSError):
        return ''
    if not detail:
        try:
            detail = (body or b'').decode('utf-8', 'replace')[:_ERROR_DETAIL_MAX]
        except (AttributeError, TypeError):
            return ''
    return detail[:_ERROR_DETAIL_MAX]


# A URL's host, for connection error messages
def _url_host(url):
    return urlsplit(url).netloc
