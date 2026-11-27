from __future__ import annotations
from typing import Generator, ClassVar
from types import TracebackType
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from datetime import datetime
import struct

from .address import CacheAddress, new_address
from .utils import BinaryReader, ReadableBuffer
from ..opener import custom_open
from ..time import timestamp_from_microseconds

__all__ = ["IndexHeader", "IndexFile", "ListIndex", "LruData"]

INDEX_HEADER_MAGIC = 0xC103CAC3


class ListIndex(IntEnum):
    NO_USE = 0
    LOW_USE = 1
    HIGH_USE = 2
    RESERVED = 3
    DELETED = 4


@dataclass
class LruData:
    SIZE_BYTES: ClassVar[int] = 112

    filled: bool
    sizes: list[int]
    heads: list[CacheAddress]
    tails: list[CacheAddress]
    transaction: CacheAddress
    operation: int
    operation_list: int

    @classmethod
    def unpack_from(
        cls, dir: Path, buffer: ReadableBuffer, offset: int = 0
    ) -> "LruData":
        values = struct.unpack_from("=2ii5i5I5IIii7i", buffer, offset)

        heads = [new_address(dir, v) for v in values[8:13]]
        tails = [new_address(dir, v) for v in values[13:18]]
        transaction = new_address(dir, values[18])

        return cls(
            filled=bool(values[2]),
            sizes=list(values[3:8]),
            heads=heads,
            tails=tails,
            transaction=transaction,
            operation=values[19],
            operation_list=values[20],
        )

    @classmethod
    def read_from(cls, dir: Path, file: BinaryReader) -> "LruData":
        data = file.read(cls.SIZE_BYTES) or b""
        return cls.unpack_from(dir, data)


@dataclass
class IndexHeader:
    SIZE_BYTES: ClassVar[int] = 368

    magic: int
    version: int
    num_entries: int
    # old_v2_num_bytes: int
    last_file: int
    this_id: int
    stats: CacheAddress
    table_len: int
    crash: bool
    # experiment: int
    create_time: datetime
    num_bytes: int
    corruption_detected: bool
    lru: LruData

    @classmethod
    def unpack_from(
        cls, dir: Path, buffer: ReadableBuffer, offset: int = 0
    ) -> "IndexHeader":
        values = struct.unpack_from("=IIiiiiIiiiQqi49i", buffer, offset)

        magic: int = values[0]
        if magic != INDEX_HEADER_MAGIC:
            raise ValueError()

        table_len: int = values[7]
        if table_len == 0:
            raise ValueError()

        num_bytes: int = values[11]
        if num_bytes < 0:
            raise ValueError()

        lru = LruData.unpack_from(dir, buffer, offset + 256)
        num_entries: int = values[2]
        if sum(lru.sizes) != num_entries:
            raise ValueError()

        return cls(
            magic=magic,
            version=values[1],
            num_entries=num_entries,
            # old_v2_num_bytes=values[3],
            last_file=values[4],
            this_id=values[5],
            stats=new_address(dir, values[6]),
            table_len=table_len,
            crash=bool(values[8]),
            # experiment=values[9],
            create_time=timestamp_from_microseconds(values[10]),
            num_bytes=num_bytes,
            corruption_detected=bool(values[12]),
            lru=lru,
        )

    @classmethod
    def read_from(cls, dir: Path, file: BinaryReader) -> "IndexHeader":
        data = file.read(cls.SIZE_BYTES) or b""
        return cls.unpack_from(dir, data)


class IndexFile:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.file = custom_open(self.path)
        try:
            self.header = IndexHeader.read_from(self.path.parent, self.file)
        except:
            self.file.close()
            raise

    @property
    def dir(self) -> Path:
        return self.path.parent

    @property
    def closed(self) -> bool:
        return self.file.closed

    def close(self) -> None:
        self.file.close()

    def __enter__(self) -> "IndexFile":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self.file.close()

    def __len__(self) -> int:
        return self.header.table_len

    def __getitem__(self, key: int) -> CacheAddress:
        if key < 0 or key >= len(self):
            raise IndexError()
        self.file.seek(self.header.SIZE_BYTES + 4 * key)
        return new_address(self.dir, struct.unpack("=I", self.file.read(4))[0])

    def __iter__(self) -> Generator[CacheAddress, None, None]:
        self.file.seek(self.header.SIZE_BYTES)
        for _ in range(self.header.table_len):
            yield new_address(self.dir, struct.unpack("=I", self.file.read(4))[0])
