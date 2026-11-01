# Licensed under the MIT License
# https://github.com/craigahobbs/ollama-chat/blob/main/LICENSE

"""
Markdown-to-PDF export for ollama-chat, using fpdf2 and embedded DejaVu fonts.

DejaVu fonts (Bitstream Vera plus additions, free for redistribution) cover the Cyrillic
letters and Latin-2 diacritics used by the chat, so no external font tooling or
OS-specific printing stack is needed.
"""

import pathlib
import re

from fpdf import FPDF
from fpdf.enums import XPos, YPos


# The vendored fonts directory
FONTS_DIR = pathlib.Path(__file__).parent / 'static' / 'fonts'

# Font file names by (family, style)
FONT_FILES = { \
    ('sans', ''): 'DejaVuSans.ttf', \
    ('sans', 'B'): 'DejaVuSans-Bold.ttf', \
    ('sans', 'I'): 'DejaVuSans-Oblique.ttf', \
    ('sans', 'BI'): 'DejaVuSans-BoldOblique.ttf', \
    ('mono', ''): 'DejaVuSansMono.ttf', \
    ('mono', 'B'): 'DejaVuSansMono-Bold.ttf' \
}


# Text colors - grayscale, 0 is black and 255 is white
_COLOR_TEXT = 25
_COLOR_MUTED = 100
_COLOR_CODE_FILL = 245


class _MarkdownPDF(FPDF):
    "FPDF document with a page-number footer"

    __slots__ = ()


    def footer(self):
        self.set_y(-12)
        self.set_font('sans', '', 8)
        self.set_text_color(_COLOR_MUTED)
        self.cell(0, 8, str(self.page_no()), align='R')


# Create a configured, empty PDF document
def create_pdf():
    pdf = _MarkdownPDF(format='A4')
    pdf.set_margins(18, 15, 18)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Add all our font variants - the device fallback fonts (like Helvetica+) may not have
    # Latin-2 glyphs
    for (family, style), font_file in FONT_FILES.items():
        pdf.add_font(family, style, str(FONTS_DIR / font_file))
    return pdf


# Render a markdown-ish text to PDF bytes
def render_pdf(markdown_text):
    return _render_blocks(_parse_blocks(markdown_text.splitlines()))


# Parse markdown lines into blocks
#
#   ('blank',)
#   ('heading', level, text)
#   ('paragraph', text)
#   ('list', [(marker, text), ...])  - marker is 'bullet' or the numbered item marker
#   ('quote', text)
#   ('code', [line, ...])
#   ('table', header, rows)  - header is None or a list of cell texts, rows are lists
#   ('rule',)
def _parse_blocks(lines):
    blocks = []
    ix = 0
    while ix < len(lines):
        line = lines[ix]

        # Code fence?
        if line.startswith('```'):
            code_lines = []
            ix += 1
            while ix < len(lines) and not lines[ix].startswith('```'):
                code_lines.append(lines[ix])
                ix += 1
            blocks.append(('code', code_lines))
            ix += 1
            continue

        # Table?
        if line.lstrip().startswith('|') and ix + 1 < len(lines) and _is_table_separator(lines[ix + 1]):
            (header, rows, ix) = _parse_table(lines, ix)
            blocks.append(('table', header, rows))
            continue

        # Heading?
        heading_match = re.match(r'^(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if heading_match:
            blocks.append(('heading', len(heading_match.group(1)), heading_match.group(2)))
            ix += 1
            continue

        # Horizontal rule?
        if _is_rule(line):
            blocks.append(('rule',))
            ix += 1
            continue

        # List?
        list_item_match = _match_list_item(line)
        if list_item_match is not None:
            list_items = [list_item_match]
            ix += 1
            while ix < len(lines) and (next_item := _match_list_item(lines[ix])) is not None:
                list_items.append(next_item)
                ix += 1
            blocks.append(('list', list_items))
            continue

        # Block quote?
        if line.startswith('>'):
            quote_lines = []
            while ix < len(lines) and lines[ix].startswith('>'):
                quote_lines.append(re.sub(r'^>\s?', '', lines[ix]))
                ix += 1
            blocks.append(('quote', '\n'.join(quote_lines)))
            continue

        # Blank line?
        if not line.strip():
            blocks.append(('blank',))
            ix += 1
            continue

        # Paragraph line - fold consecutive plain lines into one paragraph. Always consume
        # at least one line, so an unexpected block-looking line (like a stray "|") can not
        # loop forever.
        paragraph = [line.strip()]
        ix += 1
        while ix < len(lines) and not _is_block_line(lines[ix]):
            paragraph.append(lines[ix].strip())
            ix += 1
        blocks.append(('paragraph', ' '.join(paragraph)))

    return blocks


# Does the line start a new block (heading, list, quote, code fence, table, rule, blank)?
def _is_block_line(line):
    return bool( \
        line.startswith('```')
        or line.lstrip().startswith('|')
        or re.match(r'^#{1,6}\s', line)
        or _match_list_item(line) is not None
        or line.startswith('>')
        or _is_rule(line)
        or not line.strip()
    )


# Is the line a horizontal rule?
def _is_rule(line):
    return re.fullmatch(r'(\s*)((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})', line) is not None


# Match a list item - returns (marker, text) or None
def _match_list_item(line):
    match = re.match(r'^\s*([-*+])\s+(.*)$', line)
    if match:
        return ('bullet', match.group(2))
    match = re.match(r'^\s*(\d+[.)])\s+(.*)$', line)
    return (match.group(1), match.group(2)) if match else None


# Is the line a GFM table separator?
def _is_table_separator(line):
    cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
    return bool(cells) and all(re.fullmatch(r':?-{3,}:?', cell) for cell in cells)


# Parse a markdown table - returns (header, rows, next index)
def _parse_table(lines, ix):
    header = _table_cells(lines[ix])
    ix += 2
    rows = []
    while ix < len(lines) and lines[ix].lstrip().startswith('|'):
        rows.append(_table_cells(lines[ix]))
        ix += 1
    return (header, rows, ix)


# Split a table row into cells
def _table_cells(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


# Render parsed blocks to PDF bytes
def _render_blocks(blocks):
    pdf = create_pdf()
    for block in blocks:
        kind = block[0]
        if kind == 'blank':
            pdf.ln(2)
        elif kind == 'heading':
            _render_heading(pdf, block[1], block[2])
        elif kind == 'paragraph':
            _render_paragraph(pdf, block[1])
        elif kind == 'list':
            _render_list(pdf, block[1])
        elif kind == 'quote':
            _render_quote(pdf, block[1])
        elif kind == 'code':
            _render_code(pdf, block[1])
        elif kind == 'table':
            _render_table(pdf, block[1], block[2])
        elif kind == 'rule':
            _render_rule(pdf)
    return pdf.output()


# Render a horizontal rule
def _render_rule(pdf):
    pdf.ln(2)
    pdf.set_draw_color(_COLOR_MUTED)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)


# Render a heading block
def _render_heading(pdf, level, text):
    sizes = {1: 15, 2: 13, 3: 12, 4: 11, 5: 10.5, 6: 10}
    pdf.ln(5 if level == 1 else 3)
    pdf.set_font('sans', 'B', sizes.get(level, 10))
    pdf.set_text_color(0)
    pdf.multi_cell(0, 6, _pdf_inline(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


# Render a paragraph block
def _render_paragraph(pdf, text):
    pdf.set_font('sans', '', 10)
    pdf.set_text_color(_COLOR_TEXT)
    pdf.multi_cell(0, 5, _pdf_inline(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


# Render a list block
def _render_list(pdf, list_items):
    pdf.set_font('sans', '', 10)
    pdf.set_text_color(_COLOR_TEXT)
    indent = 6
    for (marker, text) in list_items:
        marker_text = '\u2022' if marker == 'bullet' else marker
        pdf.cell(indent, 5, marker_text, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.multi_cell(0, 5, _pdf_inline(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)


# Render a block quote - gray italic text with a light background
def _render_quote(pdf, text):
    pdf.set_font('sans', 'I', 10)
    pdf.set_text_color(_COLOR_MUTED)
    prev_fill = pdf.fill_color
    pdf.set_fill_color(_COLOR_CODE_FILL)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 5, _pdf_inline(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.fill_color = prev_fill
    pdf.ln(1)


# Render a code block - monospace text with a light background
def _render_code(pdf, code_lines):
    pdf.set_font('mono', '', 8.5)
    prev_fill = pdf.fill_color
    pdf.set_fill_color(_COLOR_CODE_FILL)
    pdf.multi_cell(0, 4.6, '\n'.join(code_lines), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    pdf.fill_color = prev_fill
    pdf.ln(1)


# Render a table block
def _render_table(pdf, header, rows):
    pdf.set_font('sans', '', 9)
    pdf.set_text_color(_COLOR_TEXT)
    with pdf.table(text_align='LEFT', line_height=4.6, padding=1.5, first_row_as_headings=header is not None) as table:

        # The header row, if the markdown table has one
        if header is not None:
            head_row = table.row()
            for cell in header:
                head_row.cell(_pdf_inline(cell))

        # The body rows
        for data_row in rows:
            body_row = table.row()
            for cell in data_row:
                body_row.cell(_pdf_inline(cell))
    pdf.ln(2)


# A task-safe, URL-safe filename slug for an export file
def export_filename(title, ext='pdf'):
    filename = re.sub(r'[\'"]', '', title.lower())
    filename = re.sub(r'[^a-z0-9]+', '-', filename).strip('-') or 'export'
    return f'{filename}.{ext}'


# Write PDF bytes to the workspace's exports directory (created if needed)
def write_pdf_file(workspace, markdown_text, title):
    exports_dir = pathlib.Path(workspace, 'exports')
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Find an unused filename
    base = export_filename(title)
    ix = 0
    while True:
        path = exports_dir / (base if not ix else base[:-4] + f'-{ix}.pdf')
        if not path.exists():
            break
        ix += 1

    with open(path, 'wb') as pdf_fh:
        pdf_fh.write(render_pdf(markdown_text))
    return path


# The markdown export text of a conversation, as rendered to PDF
def conversation_markdown(conversation):
    parts = [f"# {conversation['title']}", '', f"**Model:** {conversation['model']}"]
    for exchange in conversation.get('exchanges') or []:
        parts += ['', '## User:', '', exchange.get('user', ''), '', '## Model:', '', exchange.get('model', '')]
    return '\n'.join(parts)


# Convert markdown inline to fpdf2's inline markdown dialect (**bold**, __italic__)
def _pdf_inline(text):
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', r'\1', text)  # images -> alt text
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', text)  # links -> text (URL)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'__\1__', text)  # *italic* -> __italic__
    return text.replace('`', '')
