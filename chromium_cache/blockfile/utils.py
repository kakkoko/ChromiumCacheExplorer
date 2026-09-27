from typing import Callable, Iterator, Protocol
from types import TracebackType
from io import FileIO
import sys

__all__ = [
    "BinaryReader",
    "ReadableBuffer",
    "WriteableBuffer",
    "custom_open",
    "key2url",
]

_OPENER: Callable[[str, int], int] | None = None

if sys.platform == "win32":
    from .win32 import win32_make_opener

    _OPENER = win32_make_opener()


def custom_open(*args, **kwds) -> FileIO:
    kwds["mode"] = "rb"
    kwds["opener"] = _OPENER
    return open(*args, **kwds)


ReadableBuffer = bytes | bytearray | memoryview
WriteableBuffer = bytearray | memoryview


class BinaryReader(Protocol):
    def __iter__(self) -> Iterator[bytes]: ...
    def __next__(self) -> bytes: ...
    def __enter__(self) -> "BinaryReader": ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
    def close(self) -> None: ...
    def readable(self) -> bool: ...
    def read(self, size: int = -1, /) -> bytes | None: ...
    def readline(self, size: int | None = -1, /) -> bytes: ...
    def readlines(self, hint: int = -1, /) -> list[bytes]: ...
    def readinto(self, buffer: WriteableBuffer, /) -> int | None: ...
    def seek(self, offset: int, whence: int = 0, /) -> int: ...
    def seekable(self) -> bool: ...
    def tell(self) -> int: ...
    def __del__(self) -> None: ...
    @property
    def closed(self) -> bool: ...


def key2url(key: bytes) -> str:
    credential_key_end = key.index(b"/")
    post_key_end = key.index(b"/", credential_key_end + 1)
    if key.startswith(b"_dk_", post_key_end + 1):
        return key[key.rindex(b" ") + 1 :].decode()
    return key[post_key_end + 1 :].decode()
