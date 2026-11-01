# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
Ollama Chat PDF export unit tests
"""

import os
import unittest

from ollama_chat.pdf import _parse_blocks, conversation_markdown, export_filename, render_pdf, \
    write_pdf_file

from .util import create_test_files

# Cyrillic and Polish test text
_TEST_TEXT = '''\
# Привет, мир!

Zażółć gęślą jaźń.

## Раздел

- Первый пункт
- Второй пункт
1. Номер один
2. Номер два

> Цитата с кириллицей

```python
print('Привет, ' + 'мир')
```

| Столбец | Данные |
| ------- | ------ |
| Дата    | 2026   |

---

Финальный **абзац** и *код* `x = 1`.
'''


class TestParseBlocks(unittest.TestCase):

    def test_blocks(self):
        blocks = _parse_blocks(_TEST_TEXT.splitlines())
        self.assertListEqual( \
            [block for block in blocks if block[0] != 'blank'], \
            [
                ('heading', 1, 'Привет, мир!'),
                ('paragraph', 'Zażółć gęślą jaźń.'),
                ('heading', 2, 'Раздел'),
                ('list', [('bullet', 'Первый пункт'), ('bullet', 'Второй пункт'), ('1.', 'Номер один'), ('2.', 'Номер два')]),
                ('quote', 'Цитата с кириллицей'),
                ('code', ["print('Привет, ' + 'мир')"]),
                ('table', ['Столбец', 'Данные'], [['Дата', '2026']]),
                ('rule',),
                ('paragraph', 'Финальный **абзац** и *код* `x = 1`.')
            ]
        )


    def test_blocks_fold_paragraph(self):
        blocks = _parse_blocks(['line 1', 'line 2'])
        self.assertEqual(blocks, [('paragraph', 'line 1 line 2')])


    def test_blocks_heading_levels(self):
        blocks = _parse_blocks(['# one', '## two', '### three', '#### four', '##### five', '###### six'])
        self.assertEqual(
            blocks,
            [
                ('heading', 1, 'one'),
                ('heading', 2, 'two'),
                ('heading', 3, 'three'),
                ('heading', 4, 'four'),
                ('heading', 5, 'five'),
                ('heading', 6, 'six')
            ]
        )


    def test_blocks_table_no_header(self):
        blocks = _parse_blocks(['| a |', '| --- |', '| b |'])
        self.assertEqual(blocks, [('table', ['a'], [['b']])])


    def test_blocks_table_stray_row(self):
        # A "|" line not followed by a table separator is plain text, not a table (no hang)
        blocks = _parse_blocks(['| just text |', 'more text'])
        self.assertEqual(blocks, [('paragraph', '| just text | more text')])


    def test_blocks_unclosed_code(self):
        blocks = _parse_blocks(['```', 'code line'])
        self.assertEqual(blocks, [('code', ['code line'])])


class TestRenderPDF(unittest.TestCase):

    def test_render_cyrillic(self):
        # Render the required Cyrillic + Polish test text - DejaVu (with Cyrillic + Latin-2
        # glyphs) must be embedded in the PDF
        data = render_pdf(_TEST_TEXT)
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertIn(b'DejaVuSans', data)


    def test_render_empty(self):
        self.assertTrue(render_pdf('').startswith(b'%PDF'))


class TestExport(unittest.TestCase):

    def test_export_filename(self):
        self.assertEqual(export_filename('My Report!'), 'my-report.pdf')
        self.assertEqual(export_filename('Привет, мир!'), 'export.pdf')
        self.assertEqual(export_filename('My  "--  Report!', 'txt'), 'my-report.txt')


    def test_write_pdf_file(self):
        with create_test_files([]) as temp_dir:
            path = write_pdf_file(temp_dir, '# Title\n\nПривет, мир!', 'My Report')
            self.assertEqual(str(path), os.path.join(temp_dir, 'exports', 'my-report.pdf'))
            self.assertTrue(os.path.isfile(path))
            with open(path, 'rb') as pdf_fh:
                self.assertTrue(pdf_fh.read().startswith(b'%PDF'))

            # A second export with the same title gets a unique name
            path2 = write_pdf_file(temp_dir, '', 'My Report')
            self.assertEqual(str(path2), os.path.join(temp_dir, 'exports', 'my-report-1.pdf'))


class TestConversationMarkdown(unittest.TestCase):

    def test_conversation_markdown(self):
        conversation = {
            'title': 'Conversation 1',
            'model': 'llm',
            'exchanges': [
                {'user': 'Hello', 'model': 'Hi there'},
                {'user': 'Привет', 'model': 'Zażółć'}
            ]
        }
        self.assertEqual(
            conversation_markdown(conversation),
            '\n'.join([
                '# Conversation 1',
                '',
                '**Model:** llm',
                '',
                '## User:',
                '',
                'Hello',
                '',
                '## Model:',
                '',
                'Hi there',
                '',
                '## User:',
                '',
                'Привет',
                '',
                '## Model:',
                '',
                'Zażółć'
            ])
        )
