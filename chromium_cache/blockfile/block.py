from __future__ import annotations
from typing import ClassVar
from types import TracebackType
from dataclasses import dataclass
from pathlib import Path
import struct

from .utils import BinaryReader, ReadableBuffer
from ..opener import custom_open

__all__ = ["BlockFile"]

BLOCK_FILE_HEADER_MAGIC = 0xC104CAC3


@dataclass
class BlockFileHeader:
    SIZE_BYTES: ClassVar[int] = 8192

    magic: int
    version: int
    this_file: int
    next_file: int
    entry_size: int
    num_entries: int
    max_entries: int
    # empty: list[int]
    # hints: list[int]
    updating: bool
    # user: list[int]
    allocation_map: list[int]

    @classmethod
    def unpack_from(cls, buffer: ReadableBuffer, offset: int = 0) -> "BlockFileHeader":
        values = struct.unpack_from("=IIhhiii4i4ii5i2028I", buffer, offset)

        magic = values[0]
        if magic != BLOCK_FILE_HEADER_MAGIC:
            raise ValueError()

        this_file: int = values[2]
        if this_file < 0:
            raise ValueError()

        next_file: int = values[3]
        if next_file < 0:
            raise ValueError()

        return cls(
            magic=magic,
            version=values[1],
            this_file=this_file,
            next_file=next_file,
            entry_size=values[4],
            num_entries=values[5],
            max_entries=values[6],
            # empty=values[7:11],
            # hints=values[11:15],
            updating=bool(values[15]),
            # user=values[16:21],
            allocation_map=list(values[21:2049]),
        )

    @classmethod
    def read_from(cls, file: BinaryReader) -> "BlockFileHeader":
        data = file.read(cls.SIZE_BYTES)
        assert data is not None
        return cls.unpack_from(data)


class BlockFile:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.file = custom_open(self.path)
        try:
            self.header = BlockFileHeader.read_from(self.file)
        except:
            self.file.close()
            raise

    @property
    def closed(self) -> bool:
        return self.file.closed

    def close(self) -> None:
        self.file.close()

    def __enter__(self) -> "BlockFile":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self.file.close()

    def allocated(self, index: int, n_blocks: int = 1) -> bool:
        if index < 0 or index >= self.header.max_entries:
            raise ValueError()
        if n_blocks < 1 or n_blocks > 4:
            raise ValueError()
        if (index % 4) + n_blocks > 4:
            raise ValueError()

        div, mod = divmod(index, 32)
        bitmap = self.header.allocation_map[div]
        mask = ((1 << (n_blocks + 1)) - 1) << (mod)
        return bitmap & mask == mask

    def read(self, index: int, n_blocks: int = 1) -> bytes:
        if not self.allocated(index, n_blocks):
            raise ValueError()

        offset = self.header.SIZE_BYTES + self.header.entry_size * index
        size = self.header.entry_size * n_blocks

        self.file.seek(offset)
        data = self.file.read(size)
        if len(data) != size:
            raise ValueError()
        return data

    @property
    def number(self) -> int:
        return self.header.this_file

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def next_number(self) -> int | None:
        if self.header.next_file == 0:
            return None
        return self.header.next_file

    @property
    def next_filename(self) -> str | None:
        n = self.next_number
        if n is None:
            return None
        return f"data_{n}"

    @property
    def next_path(self) -> Path | None:
        filename = self.next_filename
        if filename is None:
            return None
        return self.path.parent / filename

    @property
    def total_blocks(self) -> int:
        return self.header.max_entries
