"""
String formatting utilities.

Provides helpers for formatting various data types into human-readable strings.
"""


def format_bytes(size: int) -> str:
    """
    Convert bytes to human-readable format (KB, MB, GB, TB).

    Args:
        size: Size in bytes to format

    Returns:
        Human-readable string representation of the byte size

    Examples:
        >>> format_bytes(1536)
        '1.5 KB'
        >>> format_bytes(1024)
        '1.0 KB'
        >>> format_bytes(0)
        '0 B'
        >>> format_bytes(1024 * 1024)
        '1.0 MB'
        >>> format_bytes(1024 * 1024 * 1024)
        '1.0 GB'
        >>> format_bytes(-1024)
        '-1.0 KB'
    """
    # Handle edge cases
    if size == 0:
        return "0 B"

    # Handle negative values
    is_negative = size < 0
    size = abs(size)

    # Define units and their byte values
    units = [
        ("TB", 1024 ** 4),
        ("GB", 1024 ** 3),
        ("MB", 1024 ** 2),
        ("KB", 1024),
        ("B", 1)
    ]

    # Find the appropriate unit
    for unit_name, unit_size in units:
        if size >= unit_size:
            value = size / unit_size
            # Format with 1 decimal place, but remove trailing .0
            formatted_value = f"{value:.1f}".rstrip('0').rstrip('.')
            result = f"{formatted_value} {unit_name}"
            return f"-{result}" if is_negative else result

    # Fallback (should never reach here due to the 'B' unit)
    return f"{'-' if is_negative else ''}{size} B"


def format_duration(seconds: float) -> str:
    """
    Convert seconds to human-readable format.

    Args:
        seconds: Duration in seconds to format

    Returns:
        Human-readable string representation of the duration

    Examples:
        >>> format_duration(90.5)
        '1m 30s'
        >>> format_duration(3661.0)
        '1h 1m 1s'
        >>> format_duration(0.0)
        '0s'
        >>> format_duration(30.0)
        '30s'
        >>> format_duration(120.0)
        '2m'
        >>> format_duration(3600.0)
        '1h'
        >>> format_duration(-30.5)
        '-30s'
    """
    # Handle edge cases
    if seconds == 0:
        return "0s"

    # Handle negative values
    is_negative = seconds < 0
    seconds = abs(seconds)

    # Convert to integer seconds (round to nearest second)
    total_seconds = int(round(seconds))

    # Calculate hours, minutes, and seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    remaining_seconds = total_seconds % 60

    # Build the result string
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if remaining_seconds > 0 or not parts:  # Include seconds if it's the only unit or if there are remaining seconds
        parts.append(f"{remaining_seconds}s")

    result = " ".join(parts)
    return f"-{result}" if is_negative else result