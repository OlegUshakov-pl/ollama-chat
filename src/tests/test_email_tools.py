# Licensed under the MIT License
# https://github.com/craigahobbs/craigahobbs.github.io/blob/main/LICENSE

"""
The ollama-chat email tools unit tests
"""

import imaplib
import json
import os
import smtplib
import unittest
from unittest import mock

from ollama_chat.email_tools import _load_env, check_email, send_email

from .util import create_test_files


_RAW_EMAIL_PLAIN = (
    'From: Alice <alice@example.com>\r\n'
    'To: boss@example.com\r\n'
    'Subject: Quarterly report\r\n'
    'Date: Sun, 01 Nov 2026 10:00:00 +0000\r\n'
    'MIME-Version: 1.0\r\n'
    'Content-Type: text/plain; charset="utf-8"\r\n'
    '\r\n'
    'Hello boss, please review the attached quarter numbers.\r\n'
)

_RAW_EMAIL_HTML = (
    'From: Bob <bob@example.com>\r\n'
    'To: boss@example.com\r\n'
    'Subject: Interesting offer\r\n'
    'Date: Sun, 01 Nov 2026 11:00:00 +0000\r\n'
    'MIME-Version: 1.0\r\n'
    'Content-Type: text/html; charset="utf-8"\r\n'
    '\r\n'
    '<html><body><p>Click <b>here</b> and <a href="http://spam.example.com/">win a prize</a>!</p></body></html>\r\n'
)


# A fake imaplib.IMAP4_SSL object
class _FakeIMAP():
    init_error = None
    login_error = None

    def __init__(self):
        self.login_user = None
        self.select_args = None
        self.search_args = None
        self.fetch_calls = []
        self.logged_out = False
        if _FakeIMAP.init_error is not None:
            error, _FakeIMAP.init_error = _FakeIMAP.init_error, None
            raise error


    def login(self, user, _password):
        if _FakeIMAP.login_error is not None:
            error, _FakeIMAP.login_error = _FakeIMAP.login_error, None
            raise error
        self.login_user = user


    def select(self, box, readonly=False):
        self.select_args = (box, readonly)
        return 'OK', [b'123']


    def search(self, _charset, criteria):
        self.search_args = criteria
        return 'OK', [b'1 3']


    def fetch(self, message_id, spec):
        self.fetch_calls.append((message_id, spec))
        raw = _RAW_EMAIL_PLAIN if message_id == b'1' else _RAW_EMAIL_HTML
        return 'OK', [(b'1 (BODY[] {100}', raw.encode('utf-8'))]


    def logout(self):
        self.logged_out = True


# A fake smtplib.SMTP_SSL object
class _FakeSMTP():
    starttls_error = None
    login_error = None
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.messages = []
        self.starttls_called = False
        _FakeSMTP.instances.append(self)


    def starttls(self, context=None):
        self.starttls_called = True
        if _FakeSMTP.starttls_error is not None:
            error, _FakeSMTP.starttls_error = _FakeSMTP.starttls_error, None
            raise error
        return 220, b'Ready to start TLS'


    def login(self, user, _password):
        self.login_user = user
        if _FakeSMTP.login_error is not None:
            error, _FakeSMTP.login_error = _FakeSMTP.login_error, None
            raise smtplib.SMTPAuthenticationError(535, b'Bad credentials')


    def sendmail(self, from_addr, to_addrs, message):
        self.from_addr, self.to_addrs, self.message = from_addr, to_addrs, message


    def quit(self):
        self.quit_called = True


_ENV_CONTENT = (
    '# Ollama Chat email settings\n'
    'EMAIL_IMAP_HOST=imap.example.com\n'
    'EMAIL_IMAP_PORT=993\n'
    'EMAIL_SMTP_HOST=smtp.example.com\n'
    'EMAIL_SMTP_PORT=465\n'
    'EMAIL_USER="boss@example.com"\n'
    "EMAIL_PASSWORD='secret'\n"
)


class TestLoadEnv(unittest.TestCase):

    def test_load_env(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            env = _load_env(temp_dir)
            self.assertEqual(env['EMAIL_IMAP_HOST'], 'imap.example.com')
            self.assertEqual(env['EMAIL_USER'], 'boss@example.com')
            self.assertEqual(env['EMAIL_PASSWORD'], 'secret')


    def test_load_env_missing(self):
        with create_test_files([]) as temp_dir:
            self.assertEqual(_load_env(temp_dir), {})


    def test_check_email_missing_config(self):
        with create_test_files([]) as temp_dir:
            with self.assertRaises(ValueError) as caught:
                check_email(workspace=temp_dir)
            self.assertIn('Email is not configured', str(caught.exception))
            self.assertIn('.env', str(caught.exception))


    def test_workspace_env_priority(self):
        test_files = [('.env', _ENV_CONTENT)]
        with create_test_files(test_files) as temp_dir:
            with create_test_files([('.env', 'EMAIL_IMAP_HOST=other\nEMAIL_IMAP_PORT=993\nEMAIL_USER=other@example.com\nEMAIL_PASSWORD=pw\n')]) as other_dir:
                imap = _FakeIMAP()
                with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                    check_email(workspace=other_dir)
                self.assertEqual(imap.login_user, 'other@example.com')


class TestCheckEmail(unittest.TestCase):

    def test_check_email(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                messages = check_email(workspace=temp_dir)
            self.assertEqual(imap.select_args, ('INBOX', True))
            self.assertEqual(imap.search_args, 'UNSEEN')
            self.assertTrue(imap.logged_out)
            # The most recent emails come first
            self.assertListEqual(
                messages,
                [
                    {
                        'from': 'Bob <bob@example.com>',
                        'subject': 'Interesting offer',
                        'date': 'Sun, 01 Nov 2026 11:00:00 +0000',
                        'excerpt': 'Click here and win a prize !'
                    },
                    {
                        'from': 'Alice <alice@example.com>',
                        'subject': 'Quarterly report',
                        'date': 'Sun, 01 Nov 2026 10:00:00 +0000',
                        'excerpt': 'Hello boss, please review the attached quarter numbers.'
                    }
                ]
            )
            self.assertListEqual(imap.fetch_calls, [(b'3', '(BODY.PEEK[])'), (b'1', '(BODY.PEEK[])')])


    def test_check_email_unread_only_false(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                check_email(unread_only=False, workspace=temp_dir)
            self.assertEqual(imap.search_args, 'ALL')


    def test_check_email_cwd_env(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            previous_dir = os.getcwd()
            os.chdir(temp_dir)
            try:
                imap = _FakeIMAP()
                with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                    check_email()
                self.assertEqual(imap.login_user, 'boss@example.com')
            finally:
                os.chdir(previous_dir)


    def test_check_email_no_messages(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b''])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                self.assertEqual(check_email(workspace=temp_dir), [])


    def test_check_email_connect_error(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', side_effect=OSError('refused')):
                with self.assertRaises(ValueError) as caught:
                    check_email(workspace=temp_dir)
            self.assertIn('cannot connect to the IMAP server "imap.example.com:993"', str(caught.exception))


    def test_check_email_login_error(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            _FakeIMAP.login_error = imaplib.IMAP4.error('LOGIN failed.')
            try:
                with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=_FakeIMAP()):
                    with self.assertRaises(ValueError) as caught:
                        check_email(workspace=temp_dir)
            finally:
                _FakeIMAP.login_error = None
            self.assertIn('IMAP login failed for "boss@example.com"', str(caught.exception))
            self.assertIn('EMAIL_USER and EMAIL_PASSWORD', str(caught.exception))


class TestCheckEmailLimit(unittest.TestCase):

    def test_check_email_limit(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b'1 2 3 4 5'])
            imap.fetch = lambda _mid, _spec: \
                ('OK', [(b'1 (BODY[] {16}', _RAW_EMAIL_PLAIN.encode('utf-8'))])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                self.assertEqual(len(check_email(limit=2, workspace=temp_dir)), 2)


    def test_check_email_limit_clamped(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b'1 2 3'])
            imap.fetch = lambda _mid, _spec: \
                ('OK', [(b'1 (BODY[] {16}', _RAW_EMAIL_PLAIN.encode('utf-8'))])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                self.assertEqual(len(check_email(limit=100, workspace=temp_dir)), 3)


    def test_check_email_bad_limit(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b'1 2'])
            imap.fetch = lambda _mid, _spec: \
                ('OK', [(b'1 (BODY[] {16}', _RAW_EMAIL_PLAIN.encode('utf-8'))])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                self.assertEqual(len(check_email(limit='foo', workspace=temp_dir)), 2)


    def test_check_email_long_excerpt(self):
        raw = _RAW_EMAIL_PLAIN + ('x' * 3000 + '\r\n')
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b'1'])
            imap.fetch = lambda _mid, _spec: ('OK', [(b'1 (BODY[] {3000}', raw.encode('utf-8'))])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                messages = check_email(workspace=temp_dir)
            self.assertEqual(len(messages[0]['excerpt']), 1000)


    def test_check_email_no_html_tags_needed(self):
        # A text/plain part is not HTML-stripped
        raw = (
            'From: Alice <alice@example.com>\r\n'
            'Subject: Code sample\r\n'
            'Date: Sun, 01 Nov 2026 10:00:00 +0000\r\n'
            'Content-Type: text/plain; charset="utf-8"\r\n'
            '\r\n'
            'Use <html> tags in code.\r\n'
        )
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b'1'])
            imap.fetch = lambda _mid, _spec: ('OK', [(b'1 (BODY[] {30}', raw.encode('utf-8'))])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                messages = check_email(workspace=temp_dir)
            self.assertEqual(messages[0]['excerpt'], 'Use <html> tags in code.')


    def test_check_email_email_with_attachment_only_skipped(self):
        # An email with no body text part yields an empty excerpt
        raw = (
            'From: Alice <alice@example.com>\r\n'
            'Subject: Files\r\n'
            'Date: Sun, 01 Nov 2026 10:00:00 +0000\r\n'
            'MIME-Version: 1.0\r\n'
            'Content-Type: multipart/mixed; boundary="BOUNDARY"\r\n'
            '\r\n'
            '--BOUNDARY\r\n'
            'Content-Type: text/plain; charset="utf-8"\r\n'
            'Content-Disposition: attachment; filename="report.txt"\r\n'
            '\r\n'
            'Attached file text\r\n'
            '--BOUNDARY--\r\n'
        )
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            imap = _FakeIMAP()
            imap.search = lambda _charset, _criteria: ('OK', [b'1'])
            imap.fetch = lambda _mid, _spec: ('OK', [(b'1 (BODY[] {200}', raw.encode('utf-8'))])
            with mock.patch('ollama_chat.email_tools.imaplib.IMAP4_SSL', return_value=imap):
                messages = check_email(workspace=temp_dir)
            self.assertEqual(messages[0]['excerpt'], '')


class TestSendEmail(unittest.TestCase):

    def setUp(self):
        _FakeSMTP.instances = []


    def test_send_email_ssl(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            with mock.patch('ollama_chat.email_tools.smtplib.SMTP_SSL', _FakeSMTP):
                result = send_email('client@example.com', 'Hi', 'The body text.', workspace=temp_dir)
            self.assertEqual(result, 'Email sent to client@example.com')
        self.assertEqual(len(_FakeSMTP.instances), 1)
        smtp = _FakeSMTP.instances[0]
        self.assertEqual((smtp.host, smtp.port, smtp.timeout), ('smtp.example.com', 465, 30))
        self.assertEqual(smtp.login_user, 'boss@example.com')
        self.assertFalse(smtp.starttls_called)
        self.assertTrue(smtp.quit_called)
        self.assertEqual(smtp.from_addr, 'boss@example.com')
        self.assertEqual(smtp.to_addrs, ['client@example.com'])
        self.assertIn('Subject: Hi', smtp.message)
        self.assertIn('VGhlIGJvZHkgdGV4dC4=', smtp.message)  # base64 "The body text."


    def test_send_email_starttls(self):
        env = _ENV_CONTENT.replace('EMAIL_SMTP_PORT=465', 'EMAIL_SMTP_PORT=587')
        with create_test_files([('.env', env)]) as temp_dir:
            with mock.patch('ollama_chat.email_tools.smtplib.SMTP_SSL', _FakeSMTP), \
                 mock.patch('ollama_chat.email_tools.smtplib.SMTP', _FakeSMTP):
                send_email('client@example.com', 'Hi', 'Body', workspace=temp_dir)
        self.assertEqual(len(_FakeSMTP.instances), 1)
        smtp = _FakeSMTP.instances[0]
        self.assertEqual((smtp.host, smtp.port), ('smtp.example.com', 587))
        self.assertTrue(smtp.starttls_called)


    def test_send_email_starttls_error(self):
        env = _ENV_CONTENT.replace('EMAIL_SMTP_PORT=465', 'EMAIL_SMTP_PORT=587')
        _FakeSMTP.starttls_error = smtplib.SMTPException('no TLS')
        try:
            with create_test_files([('.env', env)]) as temp_dir:
                with mock.patch('ollama_chat.email_tools.smtplib.SMTP_SSL', _FakeSMTP), \
                     mock.patch('ollama_chat.email_tools.smtplib.SMTP', _FakeSMTP):
                    with self.assertRaises(ValueError) as caught:
                        send_email('client@example.com', 'Hi', 'Body', workspace=temp_dir)
        finally:
            _FakeSMTP.starttls_error = None
        self.assertIn('cannot start TLS', str(caught.exception))


    def test_send_email_connect_error(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            with mock.patch('ollama_chat.email_tools.smtplib.SMTP_SSL', side_effect=smtplib.SMTPException('no route')):
                with self.assertRaises(ValueError) as caught:
                    send_email('client@example.com', 'Hi', 'Body', workspace=temp_dir)
        self.assertIn('cannot connect to the SMTP server "smtp.example.com:465"', str(caught.exception))


    def test_send_email_auth_error(self):
        _FakeSMTP.login_error = smtplib.SMTPAuthenticationError(535, b'no')
        try:
            with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
                with mock.patch('ollama_chat.email_tools.smtplib.SMTP_SSL', _FakeSMTP):
                    with self.assertRaises(ValueError) as caught:
                        send_email('client@example.com', 'Hi', 'Body', workspace=temp_dir)
        finally:
            _FakeSMTP.login_error = None
        self.assertIn('SMTP login failed', str(caught.exception))


    def test_send_email_bad_address(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            with self.assertRaises(ValueError) as caught:
                send_email('not-an-address', 'Hi', 'Body', workspace=temp_dir)
        self.assertIn('invalid email address', str(caught.exception))


    def test_send_email_empty_body(self):
        with create_test_files([('.env', _ENV_CONTENT)]) as temp_dir:
            with self.assertRaises(ValueError):
                send_email('client@example.com', 'Hi', '  ', workspace=temp_dir)


__all__ = ['TestLoadEnv', 'TestCheckEmail', 'TestSendEmail']
