"""
Message formatting utilities for chat
"""
import re
from markupsafe import Markup


def format_message_content(content):
    """
    Format message content with support for:
    - Bullet points (-, *, •)
    - Numbered lists (1., 2., etc.)
    - Basic line breaks

    Returns HTML-safe formatted content.
    """
    if not content:
        return ''

    lines = content.split('\n')
    formatted_lines = []
    in_list = False
    list_type = None  # 'ul' or 'ol'

    for line in lines:
        stripped = line.strip()

        # Check for bullet points
        bullet_match = re.match(r'^[-*•]\s+(.+)$', stripped)
        if bullet_match:
            if not in_list or list_type != 'ul':
                if in_list:
                    formatted_lines.append(f'</{list_type}>')
                formatted_lines.append('<ul class="message-list">')
                in_list = True
                list_type = 'ul'
            formatted_lines.append(f'<li>{apply_inline_formatting(escape_html(bullet_match.group(1)))}</li>')
            continue

        # Check for numbered lists
        numbered_match = re.match(r'^(\d+)\.\s+(.+)$', stripped)
        if numbered_match:
            if not in_list or list_type != 'ol':
                if in_list:
                    formatted_lines.append(f'</{list_type}>')
                formatted_lines.append('<ol class="message-list">')
                in_list = True
                list_type = 'ol'
            formatted_lines.append(f'<li>{apply_inline_formatting(escape_html(numbered_match.group(2)))}</li>')
            continue

        # Regular line
        if in_list:
            formatted_lines.append(f'</{list_type}>')
            in_list = False
            list_type = None

        if stripped:
            formatted_lines.append(f'<p class="message-paragraph">{apply_inline_formatting(escape_html(stripped))}</p>')
        else:
            formatted_lines.append('<br>')

    # Close any open list
    if in_list:
        formatted_lines.append(f'</{list_type}>')

    return Markup(''.join(formatted_lines))


def escape_html(text):
    """Escape HTML to prevent XSS"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))


def apply_inline_formatting(text):
    """
    Apply markdown-style inline formatting to escaped HTML text.
    Supports:
    - **bold** or __bold__
    - *italic* or _italic_
    - `code`
    - ~~strikethrough~~
    """
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.+?)__', r'<strong>\1</strong>', text)

    # Italic: *text* or _text_ (but not if part of bold)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<em>\1</em>', text)

    # Code: `text`
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)

    # Strikethrough: ~~text~~
    text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)

    return text
