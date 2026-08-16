"""Markdown rendering for the web/PWA client.

The bot renders markdown into Telegram-compatible HTML (see
``src.utils.text.markdown_to_html``). For the web app we want real, browser
rendered HTML instead, so we use mistune's standard GFM renderer which keeps
tables, fenced code blocks, task lists and so on intact.
"""

from __future__ import annotations

import mistune
from mistune.renderers import html as mistune_html


_html_renderer = mistune.create_markdown(
    renderer=mistune_html.HTMLRenderer(escape=False),
    plugins=["table", "strikethrough", "footnotes", "task_lists"],
)


def render_markdown_html(text: str) -> str:
    """Convert markdown text to standard HTML for the web client."""
    if not text:
        return ""
    return _html_renderer(text).strip()
