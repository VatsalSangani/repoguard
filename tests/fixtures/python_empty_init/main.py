"""Fixture: a real file alongside the empty __init__.py in the same
directory, so this fixture also proves an empty file being skipped doesn't
stop the rest of the batch from being scanned normally."""
import sys


def greet() -> str:
    return "hello"
