from __future__ import annotations
from typing import Callable
from io import FileIO
import sys

__all__ = [
    "custom_open",
]

_OPENER: Callable[[str, int], int] | None = None

if sys.platform == "win32":
    from .win32 import win32_make_opener

    _OPENER = win32_make_opener()


def custom_open(*args, **kwds) -> FileIO:
    kwds["mode"] = "rb"
    kwds["opener"] = _OPENER
    return open(*args, **kwds)
