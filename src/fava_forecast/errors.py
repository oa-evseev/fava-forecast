# errors.py
"""
Custom exceptions used across fava-forecast modules.
"""


class BeanQueryError(RuntimeError):
    """Raised when bean-query execution or parsing fails."""
    pass


class PriceParseError(RuntimeError):
    """Raised when a price or rate line cannot be parsed."""
    pass
