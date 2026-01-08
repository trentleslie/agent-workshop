"""
Validation utilities for common data formats.

Provides helpers for validating email addresses and URLs.
"""

import re
from typing import Union


def validate_email(email: Union[str, None]) -> bool:
    """
    Validate email format using regex.

    Args:
        email: Email address to validate

    Returns:
        True if email format is valid, False otherwise

    Examples:
        >>> validate_email("user@example.com")
        True
        >>> validate_email("user.name+tag@example.co.uk")
        True
        >>> validate_email("invalid.email")
        False
        >>> validate_email("")
        False
        >>> validate_email(None)
        False
        >>> validate_email("user@")
        False
        >>> validate_email("@example.com")
        False
    """
    # Handle edge cases
    if not email or not isinstance(email, str):
        return False

    if not email.strip():  # Empty or whitespace-only string
        return False

    # Email regex pattern
    # This pattern validates:
    # - Local part: letters, numbers, periods, hyphens, underscores, plus signs
    # - Must have exactly one @ symbol
    # - Domain part: letters, numbers, periods, hyphens
    # - Must end with a valid TLD (2+ characters)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    try:
        return bool(re.match(email_pattern, email.strip()))
    except Exception:
        return False


def validate_url(url: Union[str, None]) -> bool:
    """
    Validate URL format.

    Args:
        url: URL to validate

    Returns:
        True if URL format is valid, False otherwise

    Examples:
        >>> validate_url("https://www.example.com")
        True
        >>> validate_url("http://example.com/path?query=value")
        True
        >>> validate_url("ftp://files.example.com")
        True
        >>> validate_url("https://subdomain.example.co.uk/path#anchor")
        True
        >>> validate_url("invalid-url")
        False
        >>> validate_url("")
        False
        >>> validate_url(None)
        False
        >>> validate_url("://invalid")
        False
        >>> validate_url("http://")
        False
    """
    # Handle edge cases
    if not url or not isinstance(url, str):
        return False

    if not url.strip():  # Empty or whitespace-only string
        return False

    # URL regex pattern
    # This pattern validates:
    # - Protocol: http, https, ftp, or other common protocols
    # - Domain: letters, numbers, periods, hyphens
    # - Optional port number
    # - Optional path, query parameters, and fragment
    url_pattern = r'^[a-zA-Z][a-zA-Z\d+\-\.]*://[a-zA-Z0-9\-\.]+(?:\:[0-9]+)?(?:/[^\s]*)?$'

    try:
        return bool(re.match(url_pattern, url.strip()))
    except Exception:
        return False