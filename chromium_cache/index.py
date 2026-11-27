from __future__ import annotations
from typing import ByteString, Generator, ClassVar
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import struct
import binascii
import hashlib

from .entry import EntryRecord
from .opener import custom_open

__all__ = ["SimpleIndex"]

INDEX_METADATA_MAGIC = 0x656E_7465_7220_796F


class IndexWriteToDiskReason(Enum):
    SHUTDOWN = 0
    STARTUP_MERGE = 1
    IDLE = 2
    ANDROID_STOPPED = 3


@dataclass
class IndexMetadata:
    LEN: ClassVar[int] = 32
    magic_number: int
    version: int
    entry_count: int
    cache_size: int
    reason: IndexWriteToDiskReason

    @classmethod
    def unpack_from(cls, buffer: ByteString, offset: int = 0) -> "IndexMetadata":
        magic_number, version, entry_count, cache_size, reason_raw = struct.unpack_from(
            "=QLQQL", buffer, offset
        )
        if magic_number != INDEX_METADATA_MAGIC:
            raise ValueError(
                f"invalid magic number: expected {INDEX_METADATA_MAGIC:016X}, actual {magic_number:016X}"
            )
        if entry_count > 1_000_000:
            raise ValueError(f"too many entries in index: {entry_count}")
        try:
            reason = IndexWriteToDiskReason(reason_raw)
        except ValueError:
            raise ValueError(f"unknown reason: {reason_raw}")
        return cls(magic_number, version, entry_count, cache_size, reason)

    def __len__(self) -> int:
        return self.LEN


class SimpleIndex:
    def __init__(
        self,
        dir: str | Path,
        metadata: IndexMetadata,
        entries: dict[int, EntryRecord],
        last_modified: datetime,
    ) -> None:
        self.base = Path(dir)
        self.meta = metadata
        self.entries = entries
        self.last_modified = last_modified

    @classmethod
    def load(cls, dir: str | Path) -> "SimpleIndex":
        cache_dir = Path(dir)
        if not cache_dir.is_dir():
            raise ValueError(f"cache directory not found: {cache_dir!s}")

        index_file = cache_dir / "index-dir" / "the-real-index"
        if not index_file.is_file():
            raise ValueError(f"cache index file not found: {index_file!s}")

        with custom_open(index_file) as src:
            data = memoryview(src.read())
        payload_size, crc = struct.unpack_from("=LL", data)
        payload = data[8:]
        if len(payload) != payload_size:
            raise ValueError(
                f"invalid payload size: expected {payload_size}, actual {len(payload)}"
            )
        if (calculated_crc := binascii.crc32(payload) & 0xFFFFFFFF) != crc:
            raise ValueError(
                f"crc32 mismatch: expected {crc:08X}, actual {calculated_crc:08X}"
            )

        metadata = IndexMetadata.unpack_from(payload)
        entries: dict[int, EntryRecord] = {}
        offset = len(metadata)
        while len(entries) < metadata.entry_count:
            entry = EntryRecord.unpack_from(payload, offset)
            entries[entry.entry_hash] = entry
            offset += len(entry)

        cache_last_modified_raw = struct.unpack_from("=Q", payload, offset)[0]
        cache_last_modified = EntryRecord.EPOCH + timedelta(
            microseconds=cache_last_modified_raw
        )

        offset += 8
        if offset != len(payload):
            raise ValueError("invalid payload size")

        return cls(cache_dir, metadata, entries, cache_last_modified)

    @classmethod
    def hash(cls, url: str) -> int:
        digest = hashlib.sha1(url.encode()).digest()
        return struct.unpack_from("=Q", digest)[0]

    def __len__(self) -> int:
        return len(self.entries)

    def __contains__(self, key: int | str) -> bool:
        n = key if isinstance(key, int) else self.hash(key)
        return n in self.entries

    def __getitem__(self, key: int | str) -> EntryRecord:
        n = key if isinstance(key, int) else self.hash(key)
        return self.entries[n]

    def __iter__(self) -> Generator[EntryRecord, None, None]:
        yield from self.entries.values()
