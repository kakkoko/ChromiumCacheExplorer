#!/usr/bin/env python3
from typing import ClassVar
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import struct

from .address import CacheAddress, new_address
from .utils import BinaryReader, ReadableBuffer
from ..time import timestamp_from_microseconds
from ..hash import persistent_hash

__all__ = ["RankingsNode"]


@dataclass
class RankingsNode:
    SIZE_BYTES: ClassVar[int] = 36

    last_used: datetime
    # no_longer_used_last_modified: datetime
    next: CacheAddress
    prev: CacheAddress
    contents: CacheAddress
    dirty: int
    self_hash: int

    @classmethod
    def unpack_from(
        cls, dir: Path, buffer: ReadableBuffer, offset: int = 0
    ) -> "RankingsNode":
        values = struct.unpack_from("=QQIIIiI", buffer, offset)

        self_hash = values[6]
        if persistent_hash(buffer[offset : offset + 32]) != self_hash:
            raise ValueError()

        return cls(
            last_used=timestamp_from_microseconds(values[0]),
            # no_longer_used_last_modified=timestamp_from_microseconds(values[1]),
            next=new_address(dir, values[2]),
            prev=new_address(dir, values[3]),
            contents=new_address(dir, values[4]),
            dirty=values[5],
            self_hash=self_hash,
        )

    @classmethod
    def read_from(cls, dir: Path, file: BinaryReader) -> "RankingsNode":
        data = file.read(cls.SIZE_BYTES) or b""
        return cls.unpack_from(dir, data)
