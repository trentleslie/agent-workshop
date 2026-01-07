"""
Basic calculator utility module.

Provides fundamental arithmetic operations with proper error handling
and type safety.
"""

from typing import Union

Number = Union[int, float]


def add(a: Number, b: Number) -> Number:
    """
    Add two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The sum of a and b

    Examples:
        >>> add(2, 3)
        5
        >>> add(1.5, 2.5)
        4.0
        >>> add(-1, 1)
        0
    """
    return a + b


def subtract(a: Number, b: Number) -> Number:
    """
    Subtract the second number from the first.

    Args:
        a: The number to subtract from
        b: The number to subtract

    Returns:
        The difference of a and b (a - b)

    Examples:
        >>> subtract(5, 3)
        2
        >>> subtract(1.5, 0.5)
        1.0
        >>> subtract(0, 5)
        -5
    """
    return a - b


def multiply(a: Number, b: Number) -> Number:
    """
    Multiply two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        The product of a and b

    Examples:
        >>> multiply(3, 4)
        12
        >>> multiply(2.5, 2)
        5.0
        >>> multiply(-2, 3)
        -6
    """
    return a * b


def divide(a: Number, b: Number) -> Number:
    """
    Divide the first number by the second.

    Args:
        a: The dividend (number to be divided)
        b: The divisor (number to divide by)

    Returns:
        The quotient of a and b (a / b)

    Raises:
        ValueError: If b is zero (division by zero)

    Examples:
        >>> divide(10, 2)
        5.0
        >>> divide(7, 2)
        3.5
        >>> divide(-6, 3)
        -2.0
        >>> divide(5, 0)
        Traceback (most recent call last):
            ...
        ValueError: Cannot divide by zero
    """
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
