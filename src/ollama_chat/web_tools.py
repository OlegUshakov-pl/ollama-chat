# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
The ollama-chat web search and page fetch tools
"""

import html
import ipaddress
import re
import socket
import urllib.parse

import trafilatura
import urllib3

from ddgs import DDGS


# The tool definitions passed to the Ollama chat API "tools" field
WEB_TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'web_search',
            'description': 'Search the web for current information. Returns a list of matching pages ' \
                'with their titles, URLs and snippets. Use this before answering questions about ' \
                'recent events or facts that may not be in the model training data.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'query': {
                        'type': 'string',
                        'description': 'The web search query'
                    },
                    'max_results': {
                        'type': 'integer',
                        'description': 'The maximum number of results to return (default is 5)'
                    }
                },
                'required': ['query']
            }
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'fetch_page',
            'description': 'Download a web page and return its readable text content. Use this to read ' \
                'the content of a page found with web_search or a URL mentioned by the user.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'url': {
                        'type': 'string',
                        'description': 'The http or https URL of the page to read'
                    }
                },
                'required': ['url']
            }
        }
    }
]

# The default and maximum number of search results
SEARCH_MAX_RESULTS = 5

# The page fetch limits
FETCH_MAX_REDIRECTS = 5
FETCH_MAX_BYTES = 2_000_000
FETCH_MAX_CHARS = 6000

# The page fetch timeouts (seconds)
_FETCH_TIMEOUT = urllib3.Timeout(connect=5, read=10)

# Fetch pages without retries and without following redirects - redirects are followed manually so
# that every hop's URL is checked for internal addresses
_FETCH_RETRIES = urllib3.Retry(total=0, redirect=False)

# The redirect status codes
_FETCH_REDIRECT_CODES = (301, 302, 303, 307, 308)

# The shared page fetch connection pool
_FETCH_POOL = None


# Search the web and return the matching pages as [{title, url, snippet}]
def web_search(query, max_results=SEARCH_MAX_RESULTS):
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
    except Exception as exc:
        raise ValueError(f'web search failed ({exc})') from None
    return [
        {
            'title': result.get('title') or '',
            'url': result.get('href') or '',
            'snippet': result.get('body') or ''
        }
        for result in (results or [])
        if result.get('href')
    ]


# Fetch a web page and return its readable text content, truncated to FETCH_MAX_CHARS characters
def fetch_page(url, pool_manager=None):
    _check_url(url)
    pool = pool_manager if pool_manager is not None else _fetch_pool()

    # Follow redirects manually, checking every hop's URL
    current_url = url
    for _ in range(FETCH_MAX_REDIRECTS + 1):
        try:
            response = pool.request(
                'GET', current_url, retries=_FETCH_RETRIES, timeout=_FETCH_TIMEOUT, preload_content=False
            )
        except (urllib3.exceptions.HTTPError, OSError, ValueError) as exc:
            raise ValueError(f'failed to load page ({exc})') from None
        try:
            # Follow the redirect
            if response.status in _FETCH_REDIRECT_CODES:
                location = response.headers.get('Location')
                if not location:
                    raise ValueError('redirect without a location')
                current_url = urllib.parse.urljoin(current_url, location)
                _check_url(current_url)
                continue

            # Unexpected status?
            if response.status != 200:
                raise ValueError(f'unexpected HTTP status {response.status}')

            # Only fetch textual content
            content_type = response.headers.get('Content-Type') or ''
            if content_type and not any(kind in content_type for kind in ('text/', 'html', 'xml')):
                raise ValueError(f'unsupported content type "{content_type.split(";")[0].strip()}"')

            # Read the page, bounded so that huge responses aren't buffered
            data = response.read(FETCH_MAX_BYTES + 1)
            if len(data) > FETCH_MAX_BYTES:
                raise ValueError('page is too large')
            charset = _content_charset(content_type)
        finally:
            response.close()

        # Extract the readable text content
        page_text = _page_text(data.decode(charset, errors='replace'))
        if not page_text:
            raise ValueError('page has no text content')
        return page_text[:FETCH_MAX_CHARS]

    raise ValueError('too many redirects')


# The shared page fetch connection pool
def _fetch_pool():
    global _FETCH_POOL # pylint: disable=global-statement
    if _FETCH_POOL is None:
        _FETCH_POOL = urllib3.PoolManager()
    return _FETCH_POOL


# Check that a URL is fetchable - only public http/https addresses are allowed
def _check_url(url):
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        raise ValueError('invalid URL') from None
    if parts.scheme not in ('http', 'https'):
        raise ValueError('only http and https URLs are allowed')
    if not parts.hostname:
        raise ValueError('URL has no host')
    _check_host(parts.hostname)


# Check that a host resolves only to public (non-internal) addresses
def _check_host(hostname):
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(sockaddr[0])
                for _family, _type, _proto, _canonname, sockaddr in socket.getaddrinfo(hostname, None)
            ]
        except (socket.gaierror, OSError, ValueError):
            raise ValueError(f'cannot resolve host "{hostname}"') from None
        if not addresses:
            raise ValueError(f'cannot resolve host "{hostname}"')
    for address in addresses:
        if not address.is_global or address.is_multicast:
            raise ValueError('access to private or internal addresses is not allowed')


# The page's charset from its content type header (defaulting to UTF-8)
def _content_charset(content_type):
    match = _RE_CHARSET.search(content_type)
    return match.group(1) if match else 'utf-8'

_RE_CHARSET = re.compile(r'charset\s*=\s*["\']?([\w.-]+)', re.IGNORECASE)


# Extract the readable text content of a page, falling back to plain tag stripping
def _page_text(page_html):
    try:
        page_text = trafilatura.extract(page_html)
    except Exception: # pylint: disable=broad-exception-caught
        page_text = None
    if not page_text:
        page_text = _strip_html(page_html)
    return page_text.strip()


# Strip the markup from a page, used when the content extractor finds no article text
def _strip_html(page_html):
    text = _RE_SCRIPT_STYLE.sub(' ', page_html)
    text = _RE_HTML_TAG.sub(' ', text)
    return _RE_WHITESPACE.sub(' ', html.unescape(text)).strip()

_RE_SCRIPT_STYLE = re.compile(r'(?is)<(script|style|noscript)[^>]*>.*?</\s*\1\s*>')
_RE_HTML_TAG = re.compile(r'(?s)<[^>]+>')
_RE_WHITESPACE = re.compile(r'\s+')
