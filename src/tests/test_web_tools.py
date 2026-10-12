# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

import socket
import unittest
import unittest.mock

import urllib3

from ollama_chat.web_tools import fetch_page, web_search, WEB_TOOLS


# Helper to build a mock HTTP response
def mock_response(status, body=b'', headers=None):
    response = unittest.mock.Mock(spec=urllib3.response.HTTPResponse)
    response.status = status
    response.headers = headers or {}
    response.read.return_value = body
    return response


# Helper to build a mock connection pool returning the given responses in order
def mock_pool(responses):
    pool = unittest.mock.Mock(spec=urllib3.PoolManager)
    pool.request.side_effect = responses
    return pool


# Helper getaddrinfo result for a public address
def public_addrinfo(address='93.184.215.14'):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (address, 0))]


class TestWebSearch(unittest.TestCase):

    def test_web_search(self):
        results = [{'title': 'Title', 'href': 'http://example.com/', 'body': 'Snippet'}]
        with unittest.mock.patch('ollama_chat.web_tools.DDGS') as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = results
            self.assertListEqual(
                web_search('the query'),
                [{'title': 'Title', 'url': 'http://example.com/', 'snippet': 'Snippet'}]
            )
            mock_ddgs.return_value.__enter__.return_value.text.assert_called_once_with('the query', max_results=5)

    def test_web_search_max_results(self):
        with unittest.mock.patch('ollama_chat.web_tools.DDGS') as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = []
            self.assertListEqual(web_search('the query', max_results=2), [])
            mock_ddgs.return_value.__enter__.return_value.text.assert_called_once_with('the query', max_results=2)

    def test_web_search_missing_url(self):
        results = [{'title': 'Title', 'body': 'Snippet'}]
        with unittest.mock.patch('ollama_chat.web_tools.DDGS') as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = results
            self.assertListEqual(web_search('q'), [])

    def test_web_search_error(self):
        with unittest.mock.patch('ollama_chat.web_tools.DDGS') as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.side_effect = RuntimeError('no results')
            with self.assertRaises(ValueError) as raises:
                web_search('q')
            self.assertEqual(str(raises.exception), 'web search failed (no results)')

    def test_web_tools_definitions(self):
        self.assertListEqual(
            [tool['function']['name'] for tool in WEB_TOOLS],
            ['web_search', 'fetch_page']
        )


class TestWebToolsSSRF(unittest.TestCase):

    def test_reject_url_schemes(self):
        for url in ('file:///etc/passwd', 'ftp://example.com/', 'gopher://example.com/', 'javascript:alert(1)'):
            with self.subTest(url=url), self.assertRaises(ValueError) as raises:
                fetch_page(url, mock_pool([]))
            self.assertEqual(str(raises.exception), 'only http and https URLs are allowed')

    def test_reject_internal_addresses(self):
        for url in (
            'http://localhost/admin',
            'http://127.0.0.1/',
            'http://127.1.2.3:8080/',
            'http://10.0.0.1/',
            'http://172.16.0.1/',
            'http://192.168.1.1/',
            'http://169.254.169.254/latest/meta-data/',
            'http://100.64.0.1/',
            'http://0.0.0.0/',
            'http://[::1]/',
            'http://[fe80::1]/',
            'http://[fc00::1]/',
        ):
            with self.subTest(url=url), self.assertRaises(ValueError) as raises:
                fetch_page(url, mock_pool([]))
            self.assertEqual(str(raises.exception), 'access to private or internal addresses is not allowed')

    def test_reject_host_resolving_to_internal_address(self):
        addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('127.0.0.1', 0))]
        pool = mock_pool([])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=addrinfo), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://internal.example/', pool)
        self.assertEqual(str(raises.exception), 'access to private or internal addresses is not allowed')
        pool.request.assert_not_called()

    def test_reject_host_with_mixed_addresses(self):
        addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('93.184.215.14', 0)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', ('10.0.0.1', 0))
        ]
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=addrinfo), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://mixed.example/', mock_pool([]))
        self.assertEqual(str(raises.exception), 'access to private or internal addresses is not allowed')

    def test_reject_unresolvable_host(self):
        with unittest.mock.patch(
            'ollama_chat.web_tools.socket.getaddrinfo', side_effect=socket.gaierror('Name or service not known')
        ), self.assertRaises(ValueError) as raises:
            fetch_page('http://unknown.example/', mock_pool([]))
        self.assertEqual(str(raises.exception), 'cannot resolve host "unknown.example"')

    def test_reject_host_with_no_addresses(self):
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=[]), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://empty.example/', mock_pool([]))
        self.assertEqual(str(raises.exception), 'cannot resolve host "empty.example"')

    def test_reject_invalid_url(self):
        with self.assertRaises(ValueError) as raises:
            fetch_page('http://[fe80::1', mock_pool([]))
        self.assertEqual(str(raises.exception), 'invalid URL')

    def test_reject_url_without_host(self):
        with self.assertRaises(ValueError) as raises:
            fetch_page('http:///path', mock_pool([]))
        self.assertEqual(str(raises.exception), 'URL has no host')

    def test_reject_redirect_to_internal_address(self):
        response = mock_response(302, headers={'Location': 'http://127.0.0.1/admin'})
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'access to private or internal addresses is not allowed')
        self.assertEqual(pool.request.call_count, 1)


class TestFetchPage(unittest.TestCase):

    def test_fetch_page(self):
        html = '<html><head><title>Page</title></head><body><p>Hello <b>world</b></p></body></html>'
        response = mock_response(200, html.encode('utf-8'), {'Content-Type': 'text/html; charset=utf-8'})
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', return_value='Hello world'):
            self.assertEqual(fetch_page('http://public.example/', pool), 'Hello world')
        self.assertEqual(pool.request.call_count, 1)
        response.close.assert_called_once_with()

    def test_fetch_page_strip_html_fallback(self):
        html = '<html><body><p>Hello <b>world</b></p><script>var x = 1;</script></body></html>'
        response = mock_response(200, html.encode('utf-8'), {'Content-Type': 'text/html'})
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', return_value=None):
            self.assertEqual(fetch_page('http://public.example/', pool), 'Hello world')

    def test_fetch_page_extract_error_falls_back(self):
        html = '<html><body><p>Hello <b>world</b></p></body></html>'
        response = mock_response(200, html.encode('utf-8'), {'Content-Type': 'text/html'})
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch(
                 'ollama_chat.web_tools.trafilatura.extract', side_effect=RuntimeError('extract failed')
             ):
            self.assertEqual(fetch_page('http://public.example/', pool), 'Hello world')

    def test_fetch_page_default_pool(self):
        responses = [
            mock_response(200, b'<p>Content</p>', {'Content-Type': 'text/html'}),
            mock_response(200, b'<p>Content</p>', {'Content-Type': 'text/html'})
        ]
        pool = mock_pool(responses)
        with unittest.mock.patch('ollama_chat.web_tools._FETCH_POOL', None), \
             unittest.mock.patch('ollama_chat.web_tools.urllib3.PoolManager', return_value=pool), \
             unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', return_value='Content'):

            # The first fetch creates and caches the shared pool
            self.assertEqual(fetch_page('http://public.example/'), 'Content')

            # The second fetch reuses the cached pool
            self.assertEqual(fetch_page('http://public.example/'), 'Content')

        self.assertEqual(pool.request.call_count, 2)

    def test_fetch_page_truncates(self):
        response = mock_response(200, b'x' * 10000, {'Content-Type': 'text/plain'})
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', side_effect=lambda text: text):
            page_text = fetch_page('http://public.example/', pool)
        self.assertEqual(len(page_text), 6000)

    def test_fetch_page_charset(self):
        response = mock_response(200, 'café'.encode('latin-1'), {'Content-Type': 'text/html; charset="ISO-8859-1"'})
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', side_effect=lambda text: text):
            self.assertEqual(fetch_page('http://public.example/', pool), 'café')

    def test_fetch_page_follows_redirects(self):
        redirect = mock_response(302, headers={'Location': 'https://other.example/page'})
        response = mock_response(200, b'<p>Content</p>', {'Content-Type': 'text/html'})
        pool = mock_pool([redirect, response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', return_value='Content'):
            self.assertEqual(fetch_page('http://public.example/', pool), 'Content')
        self.assertEqual(pool.request.call_count, 2)
        self.assertEqual(pool.request.call_args_list[1].args[1], 'https://other.example/page')

    def test_fetch_page_too_many_redirects(self):
        responses = [
            mock_response(302, headers={'Location': f'https://other.example/{index}'})
            for index in range(10)
        ]
        pool = mock_pool(responses)
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'too many redirects')
        self.assertEqual(pool.request.call_count, 6)

    def test_fetch_page_redirect_without_location(self):
        pool = mock_pool([mock_response(302)])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'redirect without a location')

    def test_fetch_page_http_error(self):
        pool = mock_pool([mock_response(404)])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'unexpected HTTP status 404')

    def test_fetch_page_connection_error(self):
        pool = unittest.mock.Mock(spec=urllib3.PoolManager)
        pool.request.side_effect = urllib3.exceptions.MaxRetryError(None, 'http://public.example/', Exception('boom'))
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertIn('failed to load page', str(raises.exception))
        self.assertNotIn('Traceback', str(raises.exception))

    def test_fetch_page_too_large(self):
        response = mock_response(200, b'x' * 100, {'Content-Type': 'text/html'})
        response.read.return_value = b'x' * (2_000_000 + 1)
        pool = mock_pool([response])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'page is too large')

    def test_fetch_page_unsupported_content_type(self):
        pool = mock_pool([mock_response(200, b'binary', {'Content-Type': 'application/pdf'})])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'unsupported content type "application/pdf"')

    def test_fetch_page_no_text(self):
        pool = mock_pool([mock_response(200, b'<html></html>', {'Content-Type': 'text/html'})])
        with unittest.mock.patch('ollama_chat.web_tools.socket.getaddrinfo', return_value=public_addrinfo()), \
             unittest.mock.patch('ollama_chat.web_tools.trafilatura.extract', return_value=None), \
             self.assertRaises(ValueError) as raises:
            fetch_page('http://public.example/', pool)
        self.assertEqual(str(raises.exception), 'page has no text content')
