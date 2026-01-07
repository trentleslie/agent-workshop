"""
String manipulation utilities.

Provides helpers for string processing and formatting.
"""


def truncate(s: str, max_len: int = 50) -> str:
    """
    Truncate a string to a maximum length, adding '...' if needed.

    Args:
        s: The string to truncate
        max_len: Maximum length of the returned string (default: 50)

    Returns:
        The truncated string with '...' suffix if truncation occurred,
        or the original string if no truncation was needed

    Examples:
        >>> truncate("Hello world", 10)
        'Hello...'
        >>> truncate("Short", 10)
        'Short'
        >>> truncate("", 5)
        ''
        >>> truncate("Test", 3)
        'Test'
        >>> truncate("Testing", 6)
        'Tes...'
    """
    # Handle edge cases
    if not s:  # Empty string
        return s

    if max_len < 4:  # Not enough space for '...' and at least one character
        return s

    # If string fits within max_len, return as-is
    if len(s) <= max_len:
        return s

    # Truncate and add ellipsis
    return s[:max_len-3] + '...'
