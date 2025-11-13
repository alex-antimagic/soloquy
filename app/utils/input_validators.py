"""
Input validation and sanitization utilities
"""
import re
from flask import jsonify


# Maximum message length
MAX_MESSAGE_LENGTH = 10000
MAX_NAME_LENGTH = 100
MAX_EMAIL_LENGTH = 255


def validate_message_content(content):
    """
    Validate message content
    Returns: (is_valid, error_message)
    """
    if not content:
        return False, "Message content is required"

    content_str = str(content).strip()

    if len(content_str) == 0:
        return False, "Message cannot be empty"

    if len(content_str) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long (max {MAX_MESSAGE_LENGTH} characters)"

    return True, None


def sanitize_ai_input(content):
    """
    Sanitize input before sending to AI to prevent prompt injection
    Returns: (is_safe, sanitized_content or error_message)
    """
    if not content:
        return False, "Content is required"

    content_str = str(content).strip()

    # Check for prompt injection patterns
    dangerous_patterns = [
        r'ignore\s+previous\s+instructions',
        r'ignore\s+above',
        r'disregard\s+previous',
        r'system:\s*',
        r'</system>',
        r'<\|im_start\|>',
        r'<\|im_end\|>',
        r'admin\s+mode',
        r'developer\s+mode',
        r'god\s+mode',
        r'\[INST\]',
        r'\[/INST\]',
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, content_str, re.IGNORECASE):
            return False, "Message contains potentially unsafe content"

    # Check length
    if len(content_str) > MAX_MESSAGE_LENGTH:
        return False, f"Message too long (max {MAX_MESSAGE_LENGTH} characters)"

    return True, content_str


def validate_email(email):
    """
    Validate email format
    Returns: (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    email_str = str(email).strip().lower()

    if len(email_str) > MAX_EMAIL_LENGTH:
        return False, f"Email too long (max {MAX_EMAIL_LENGTH} characters)"

    # Basic email pattern
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email_str):
        return False, "Invalid email format"

    return True, email_str


def validate_name(name, field_name="Name"):
    """
    Validate name fields (first name, last name, etc.)
    Returns: (is_valid, error_message)
    """
    if not name:
        return True, None  # Names can be optional

    name_str = str(name).strip()

    if len(name_str) > MAX_NAME_LENGTH:
        return False, f"{field_name} too long (max {MAX_NAME_LENGTH} characters)"

    # Only allow letters, spaces, hyphens, and apostrophes
    name_pattern = r"^[a-zA-Z\s\-']+$"
    if not re.match(name_pattern, name_str):
        return False, f"{field_name} contains invalid characters"

    return True, name_str


def validate_password_strength(password):
    """
    Validate password meets security requirements
    Returns: (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    password_str = str(password)

    if len(password_str) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password_str) > 128:
        return False, "Password too long (max 128 characters)"

    # Check for complexity requirements
    has_uppercase = re.search(r'[A-Z]', password_str)
    has_lowercase = re.search(r'[a-z]', password_str)
    has_digit = re.search(r'\d', password_str)
    has_special = re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|`~]', password_str)

    missing_requirements = []
    if not has_uppercase:
        missing_requirements.append("one uppercase letter")
    if not has_lowercase:
        missing_requirements.append("one lowercase letter")
    if not has_digit:
        missing_requirements.append("one number")
    if not has_special:
        missing_requirements.append("one special character")

    if missing_requirements:
        return False, f"Password must contain: {', '.join(missing_requirements)}"

    return True, None


def sanitize_sql_like_pattern(pattern):
    """
    Sanitize a SQL LIKE pattern to prevent SQL injection
    """
    if not pattern:
        return ""

    # Escape special SQL LIKE characters
    sanitized = pattern.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return sanitized
