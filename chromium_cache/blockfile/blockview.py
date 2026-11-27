from __future__ import annotations
from io import BufferedReader, SEEK_SET, SEEK_CUR, SEEK_END
from pathlib import Path

from ..opener import custom_open

__all__ = ["BlockView"]

"""
class Foo(BinaryIO):
    @property
    def mode(self) -> str: ...
    @property
    def name(self) -> str: ...
"""


class BlockView(BufferedReader):
    def __init__(self, file: Path, offset: int, size: int) -> None:
        raw = custom_open(file, buffering=0)
        super().__init__(raw)
        super().seek(offset, SEEK_SET)
        self.offset = offset
        self.size = size

    def read(self, size: int | None = None) -> bytes:
        abs_offset = super().tell()
        capacity = self.size - (abs_offset - self.offset)
        if size is None or size < 0 or size >= capacity:
            size = capacity
        return super().read(size)

    def read1(self, size: int = -1) -> bytes:
        abs_offset = super().tell()
        capacity = self.size - (abs_offset - self.offset)
        if size is None or size < 0 or size >= capacity:
            size = capacity
        return super().read1(size)

    def peek(self, size: int = 0) -> bytes:
        abs_offset = super().tell()
        capacity = self.size - (abs_offset - self.offset)
        if size is None or size < 0 or size >= capacity:
            size = capacity
        return super().peek(size)

    def tell(self) -> int:
        return super().tell() - self.offset

    def seek(self, offset: int, whence: int = SEEK_SET) -> int:
        if whence == SEEK_SET:
            pos = self.offset + offset
        elif whence == SEEK_CUR:
            pos = super().tell() + offset
        elif whence == SEEK_END:
            pos = self.offset + self.size + offset
        else:
            raise ValueError()

        if pos < self.offset:
            pos = self.offset
        elif pos > self.offset + self.size:
            pos = self.offset + self.size

        return super().seek(pos, SEEK_SET) - self.offset

    @property
    def capacity(self) -> int:
        return self.size - self.tell()
