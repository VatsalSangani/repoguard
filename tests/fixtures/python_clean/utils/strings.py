"""Small string helpers with no lint issues and no secrets."""


def reverse(text: str) -> str:
    """Return `text` reversed."""
    return text[::-1]


def is_palindrome(text: str) -> bool:
    """Return True if `text` reads the same forwards and backwards."""
    normalized = text.lower().replace(" ", "")
    return normalized == reverse(normalized)
