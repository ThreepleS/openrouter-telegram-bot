"""Text processing utilities for Telegram bot."""

import re
from io import BytesIO
from typing import List, Tuple

import mistune
from mistune.renderers import html as mistune_html
from mistune.plugins.table import table as table_plugin
from PIL import Image, ImageDraw, ImageFont

from src.config.constants import TELEGRAM_MAX_MESSAGE_LENGTH


class TelegramHTMLRenderer(mistune_html.HTMLRenderer):
    """Custom HTML renderer for Telegram-compatible HTML output."""

    def paragraph(self, text: str) -> str:
        return text

    def table(self, text: str) -> str:
        return f"<table>{text}</table>"

    def table_head(self, text: str) -> str:
        return f"<thead>{text}</thead>"

    def table_body(self, text: str) -> str:
        return f"<tbody>{text}</tbody>"

    def table_row(self, text: str) -> str:
        return f"<tr>{text}</tr>"

    def table_cell(self, text: str, **kwargs) -> str:
        flags = kwargs.get("flags", {})
        head = kwargs.get("head", False)
        if flags.get("header") or head:
            return f"<th>{text}</th>"
        return f"<td>{text}</td>"

    def strikethrough(self, text: str) -> str:
        return f"<s>{text}</s>"

    def emphasis(self, text: str) -> str:
        return f"<i>{text}</i>"

    def strong(self, text: str) -> str:
        return f"<b>{text}</b>"

    def codespan(self, text: str) -> str:
        safe = text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        return f"<code>{safe}</code>"

    def link(self, text: str, **kwargs) -> str:
        url = kwargs.get("url", "")
        safe_url = url.replace("<", "").replace(">", "").replace('"', "&quot;")
        title = kwargs.get("title")
        if title:
            safe_title = title.replace("<", "").replace(">", "").replace('"', "&quot;")
            return f'<a href="{safe_url}" title="{safe_title}">{text}</a>'
        return f'<a href="{safe_url}">{text}</a>'

    def image(self, text: str = "", **kwargs) -> str:
        src = kwargs.get("src", "")
        safe_src = src.replace("<", "").replace(">", "").replace('"', "&quot;")
        alt = kwargs.get("alt", text)
        title = kwargs.get("title")
        if title:
            safe_title = title.replace("<", "").replace(">", "").replace('"', "&quot;")
            return f'<a href="{safe_src}" title="{safe_title}">{alt}</a>'
        return f'<a href="{safe_src}">{alt}</a>'

    def block_code(self, code: str, info: str = None) -> str:
        safe = code.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        if info:
            return f"<pre><code class=\"language-{info}\">{safe}</code></pre>"
        return f"<pre><code>{safe}</code></pre>"

    def linebreak(self) -> str:
        return "\n"

    def softbreak(self) -> str:
        return "\n"

    def thematic_break(self) -> str:
        return "\n"

    def heading(self, text: str, level: int = 1) -> str:
        return f"<b>{text}</b>"

    def list(self, text: str, **kwargs) -> str:
        return text

    def list_item(self, text: str, **kwargs) -> str:
        ordered = kwargs.get("ordered", False)
        index = kwargs.get("index")
        prefix = f"{index}. " if ordered and index is not None else "• "
        return f"{prefix}{text}"

    def block_html(self, html_text: str) -> str:
        return ""

    def inline_html(self, html_text: str) -> str:
        return ""


def markdown_to_html(text: str) -> str:
    """Convert markdown text to Telegram-compatible HTML."""
    markdown = mistune.create_markdown(renderer=TelegramHTMLRenderer(), plugins=[table_plugin])
    return markdown(text)


def extract_tables_from_html(html: str) -> Tuple[str, List[str]]:
    """Extract tables from HTML and return text without tables and list of table HTML."""
    table_pattern = re.compile(r"<table>.*?</table>", re.DOTALL)
    tables = table_pattern.findall(html)
    text_without_tables = table_pattern.sub("", html)
    text_without_tables = re.sub(r"\n{3,}", "\n\n", text_without_tables).strip()
    return text_without_tables, tables


def _parse_html_table(table_html: str) -> List[List[str]]:
    """Parse HTML table into list of rows (list of cell texts)."""
    rows = []
    row_pattern = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
    cell_pattern = re.compile(r"<(th|td)[^>]*>(.*?)</\1>", re.DOTALL)

    for row_match in row_pattern.finditer(table_html):
        row_html = row_match.group(1)
        cells = []
        for cell_match in cell_pattern.finditer(row_html):
            cell_text = cell_match.group(2)
            cell_text = re.sub(r"<[^>]+>", "", cell_text).strip()
            cells.append(cell_text)
        if cells:
            rows.append(cells)
    return rows


def _calculate_column_widths(rows: List[List[str]], font: ImageFont.FreeTypeFont, padding: int = 12) -> List[int]:
    """Calculate column widths based on cell content."""
    if not rows:
        return []

    num_cols = max(len(row) for row in rows)
    col_widths = [0] * num_cols

    for row in rows:
        for i, cell in enumerate(row):
            bbox = font.getbbox(cell)
            text_width = bbox[2] - bbox[0]
            col_widths[i] = max(col_widths[i], text_width + 2 * padding)

    return col_widths


def _get_unicode_font(font_size: int = 16) -> ImageFont.FreeTypeFont:
    """Get a font that supports Unicode/Cyrillic characters."""
    # Try common system fonts that support Cyrillic
    font_paths = [
        # Windows fonts
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/arialuni.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
        # Linux fonts
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        # macOS fonts
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
    ]
    
    for path in font_paths:
        try:
            return ImageFont.truetype(path, font_size)
        except OSError:
            continue
    
    # Fallback to default (won't support Cyrillic well)
    return ImageFont.load_default()


def render_table_to_png(table_html: str, font_size: int = 16, scale: int = 2) -> bytes:
    """Render HTML table to PNG image bytes using PIL with high quality."""
    rows = _parse_html_table(table_html)
    if not rows:
        return b""

    font = _get_unicode_font(font_size)
    
    # Use scaling for higher quality (render at 2x then downsample)
    render_font_size = font_size * scale
    render_padding = 12 * scale
    render_font = _get_unicode_font(render_font_size)
    
    header_bg = (0x1E, 0x3A, 0x5F)
    header_fg = (0xFF, 0xFF, 0xFF)
    row_bg_even = (0xF5, 0xF5, 0xF5)
    row_bg_odd = (0xFF, 0xFF, 0xFF)
    border_color = (0xCC, 0xCC, 0xCC)
    text_color = (0x33, 0x33, 0x33)

    col_widths = _calculate_column_widths(rows, render_font, render_padding)
    row_height = render_font_size + 2 * render_padding

    table_width = sum(col_widths) + len(col_widths) + 1
    table_height = (len(rows) + 1) * row_height + 1

    # Create image at high resolution
    img = Image.new("RGB", (table_width, table_height), color=(0xFF, 0xFF, 0xFF))
    draw = ImageDraw.Draw(img)

    x = 0
    y = 0

    # Header row
    for col_idx, col_width in enumerate(col_widths):
        draw.rectangle(
            [x, y, x + col_width, y + row_height],
            fill=header_bg,
            outline=border_color
        )
        cell_text = rows[0][col_idx] if col_idx < len(rows[0]) else ""
        bbox = render_font.getbbox(cell_text)
        text_x = x + (col_width - (bbox[2] - bbox[0])) // 2
        text_y = y + (row_height - (bbox[3] - bbox[1])) // 2
        draw.text((text_x, text_y), cell_text, font=render_font, fill=header_fg)
        x += col_width + 1

    y += row_height

    # Data rows
    for row_idx, row in enumerate(rows[1:], start=1):
        x = 0
        bg_color = row_bg_even if row_idx % 2 == 0 else row_bg_odd
        for col_idx, col_width in enumerate(col_widths):
            cell_text = row[col_idx] if col_idx < len(row) else ""
            draw.rectangle(
                [x, y, x + col_width, y + row_height],
                fill=bg_color,
                outline=border_color
            )
            bbox = render_font.getbbox(cell_text)
            text_x = x + render_padding
            text_y = y + (row_height - (bbox[3] - bbox[1])) // 2
            draw.text((text_x, text_y), cell_text, font=render_font, fill=text_color)
            x += col_width + 1
        y += row_height

    # Downscale for anti-aliasing if scale > 1
    if scale > 1:
        new_size = (table_width // scale, table_height // scale)
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    output = BytesIO()
    img.save(output, format="PNG", quality=95, optimize=True)
    return output.getvalue()

    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


def split_long_message(text: str, max_length: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> List[str]:
    """Split long message into chunks that fit within Telegram's limit."""
    if len(text) <= max_length:
        return [text]

    parts = []
    current_part = ""

    paragraphs = text.split("\n\n")

    for paragraph in paragraphs:
        if len(current_part) + len(paragraph) + 2 <= max_length:
            if current_part:
                current_part += "\n\n"
            current_part += paragraph
        else:
            if current_part:
                parts.append(current_part)
            if len(paragraph) <= max_length:
                current_part = paragraph
            else:
                lines = paragraph.split("\n")
                current_part = ""
                for line in lines:
                    if len(current_part) + len(line) + 1 <= max_length:
                        if current_part:
                            current_part += "\n"
                        current_part += line
                    else:
                        if current_part:
                            parts.append(current_part)
                        current_part = line
    if current_part:
        parts.append(current_part)

    return parts


def shorten_key(key: str, max_length: int = 20) -> str:
    """Shorten a key string to a maximum length, keeping start and end."""
    if len(key) <= max_length:
        return key
    half = (max_length - 3) // 2
    return f"{key[:half]}...{key[-half:]}"