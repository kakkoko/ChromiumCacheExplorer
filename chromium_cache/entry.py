from __future__ import annotations
from typing import ByteString, ClassVar, Generator, Protocol, TypeVar, overload
from pathlib import Path
from enum import IntFlag
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import SEEK_SET, SEEK_CUR, SEEK_END
import struct

from .opener import custom_open

__all__ = ["EntryRecord"]

INITIAL_FILE_MAGIC = 0xFCFB_6D1B_A772_5C30
FINAL_FILE_MAGIC = 0xF4FA_6F45_970D_41D8
SPARSE_RANGE_MAGIC = 0xEB97_BF01_6553_676B

T_co = TypeVar("T_co", covariant=True)


class Reader(Protocol[T_co]):
    @overload
    def read(self) -> T_co | None: ...
    @overload
    def read(self, size, /) -> T_co | None: ...


class InMemoryData(IntFlag):
    UNUSABLE_PER_CACHING_HEADERS = 1
    HIGH_PRIORITY = 2


class SimpleFileFlags(IntFlag):
    HAS_CRC32 = 1
    HAS_KEY_SHA256 = 2


@dataclass
class SimpleFileHeader:
    LEN: ClassVar[int] = 24
    initial_magic_number: int
    version: int
    key_length: int
    key_hash: int

    @classmethod
    def unpack_from(cls, buffer: ByteString, offset: int = 0) -> "SimpleFileHeader":
        initial_magic_number, version, key_length, key_hash, _ = struct.unpack_from(
            "=QLLLL", buffer, offset
        )
        if initial_magic_number != INITIAL_FILE_MAGIC:
            raise ValueError(
                f"invalid magic number: expected {INITIAL_FILE_MAGIC:016X}, actual {initial_magic_number:016X}"
            )
        return cls(initial_magic_number, version, key_length, key_hash)

    def __len__(self) -> int:
        return self.LEN


@dataclass
class SimpleFileEOF:
    LEN: ClassVar[int] = 24
    final_magic_number: int
    flags: SimpleFileFlags
    data_crc32: int
    stream_size: int

    @classmethod
    def unpack_from(cls, buffer: ByteString, offset: int = 0) -> "SimpleFileEOF":
        final_magic_number, flags, data_crc32, stream_size, _ = struct.unpack_from(
            "=QLLLL", buffer, offset
        )
        if final_magic_number != FINAL_FILE_MAGIC:
            raise ValueError(
                f"invalid magic number: expected {FINAL_FILE_MAGIC:016X}, actual {final_magic_number:016X}"
            )
        return cls(final_magic_number, SimpleFileFlags(flags), data_crc32, stream_size)

    def __len__(self) -> int:
        return self.LEN


@dataclass
class SimpleFileSparseRangeHeader:
    LEN: ClassVar[int] = 32
    sparse_range_magic_number: int
    offset: int
    length: int
    data_crc32: int

    @classmethod
    def unpack_from(
        cls, buffer: ByteString, offset: int = 0
    ) -> "SimpleFileSparseRangeHeader":
        sparse_range_magic_number, offset, length, data_crc32, _ = struct.unpack_from(
            "=QQQLL", buffer, offset
        )
        if sparse_range_magic_number != SPARSE_RANGE_MAGIC:
            raise ValueError(
                f"invalid magic number: expected {SPARSE_RANGE_MAGIC:016X}, actual {sparse_range_magic_number:016X}"
            )
        return cls(sparse_range_magic_number, offset, length, data_crc32)

    def __len__(self) -> int:
        return self.LEN


@dataclass
class SimpleFileSparseRange:
    path: Path
    key: bytes
    header: SimpleFileSparseRangeHeader
    data: bytes

    def __len__(self) -> int:
        return self.header.length


class SimpleFile:
    def __init__(
        self,
        path: str | Path,
        key: bytes,
        header: SimpleFileHeader,
        footer: SimpleFileEOF,
        offset: int,
        size: int,
    ) -> None:
        self.path = Path(path)
        self.key = key
        self.header = header
        self.footer = footer
        self.__offset = offset
        self.size = size

    def read(self) -> bytes:
        with custom_open(self.path) as f:
            f.seek(self.__offset, SEEK_SET)
            return f.read(self.size)


class EntryFile_0:
    def __init__(self, path: str | Path) -> None:
        self.__load(Path(path))

    def __load(self, path: Path) -> None:
        with custom_open(path) as f:
            header = SimpleFileHeader.unpack_from(f.read(SimpleFileHeader.LEN))
            key = f.read(header.key_length)

            f.seek(-SimpleFileEOF.LEN, SEEK_END)
            footer_0 = SimpleFileEOF.unpack_from(f.read(SimpleFileEOF.LEN))
            file_size = f.tell()

            sha256: bytes | None = None
            if SimpleFileFlags.HAS_KEY_SHA256 in footer_0.flags:
                f.seek(-(SimpleFileEOF.LEN + 32), SEEK_END)
                sha256 = f.read(32)

            offset_0 = file_size - SimpleFileEOF.LEN - footer_0.stream_size
            size_0 = footer_0.stream_size
            size_1 = (
                file_size
                - SimpleFileHeader.LEN
                - header.key_length
                - size_0
                - SimpleFileEOF.LEN * 2
            )
            offset_1 = SimpleFileHeader.LEN + header.key_length
            if sha256:
                offset_0 -= 32
                size_1 -= 32

            f.seek(offset_0 - SimpleFileEOF.LEN, SEEK_SET)
            footer_1 = SimpleFileEOF.unpack_from(f.read(SimpleFileEOF.LEN))

        self.path = path
        self.header = header
        self.key = key
        self.size = file_size
        self.stream_0 = SimpleFile(path, key, header, footer_0, offset_0, size_0)
        self.stream_1 = SimpleFile(path, key, header, footer_1, offset_1, size_1)

    def reload(self) -> None:
        self.__load(self.path)


class EntryFile_1:
    def __init__(self, path: str | Path) -> None:
        self.__load(Path(path))

    def __load(self, path: Path) -> None:
        with custom_open(path) as f:
            header = SimpleFileHeader.unpack_from(f.read(SimpleFileHeader.LEN))
            key = f.read(header.key_length)

            f.seek(-SimpleFileEOF.LEN, SEEK_END)
            footer = SimpleFileEOF.unpack_from(f.read(SimpleFileEOF.LEN))
            file_size = f.tell()
            offset = SimpleFileHeader.LEN + header.key_length
            size = (
                file_size - SimpleFileHeader.LEN - header.key_length - SimpleFileEOF.LEN
            )

        self.path = path
        self.header = header
        self.key = key
        self.size = file_size
        self.stream_2 = SimpleFile(path, key, header, footer, offset, size)

    def reload(self) -> None:
        self.__load(self.path)


class EntryFile_s:
    def __init__(self, path: str | Path) -> None:
        self.__load(Path(path))

    def __load(self, path: Path) -> None:
        ranges: list[SimpleFileSparseRangeHeader] = []
        with custom_open(path) as f:
            header = SimpleFileHeader.unpack_from(f.read(SimpleFileHeader.LEN))
            key = f.read(header.key_length)

            while True:
                blob = f.read(SimpleFileSparseRangeHeader.LEN)
                if len(blob) < SimpleFileSparseRangeHeader.LEN:
                    break
                rng = SimpleFileSparseRangeHeader.unpack_from(blob)
                ranges.append(rng)
                f.seek(rng.length, SEEK_CUR)

            file_size = f.seek(0, SEEK_END)

        self.path = path
        self.header = header
        self.key = key
        self.size = file_size
        self.__headers = ranges

    def __len__(self) -> int:
        return len(self.__headers)

    def reload(self) -> None:
        self.__load(self.path)

    def __read_range(
        self, header: SimpleFileSparseRangeHeader, file: Reader[bytes]
    ) -> SimpleFileSparseRange:
        blob = file.read(header.length)
        if blob is None:
            raise ValueError("unexpected end of file")
        return SimpleFileSparseRange(self.path, self.key, header, blob)

    def read(self, index: int) -> SimpleFileSparseRange:
        header = self.__headers[index]
        with custom_open(self.path) as f:
            f.seek(header.offset, SEEK_SET)
            return self.__read_range(header, f)

    def read_ranges(self) -> Generator[SimpleFileSparseRange, None, None]:
        with custom_open(self.path) as f:
            for header in self.__headers:
                f.seek(header.offset, SEEK_SET)
                yield self.__read_range(header, f)


@dataclass
class EntryRecord:
    LEN: ClassVar[int] = 24
    EPOCH: ClassVar[datetime] = datetime(1601, 1, 1, tzinfo=timezone.utc)
    entry_hash: int
    last_used_time: datetime
    entry_size_256b_chunks: int

    @classmethod
    def unpack_from(cls, buffer: ByteString, offset: int = 0) -> "EntryRecord":
        entry_hash, last_used_time_raw, packed_entry_info = struct.unpack_from(
            "=QQQ", buffer, offset
        )
        last_used_time = cls.EPOCH + timedelta(microseconds=last_used_time_raw)
        if packed_entry_info >> 38 != 0:
            raise ValueError(f"invalid entry info: {packed_entry_info:016X}")
        in_memory_data = InMemoryData(packed_entry_info & 0b11)
        entry_size_256b_chunks = (packed_entry_info >> 8) & 0x3FFFFFFF

        return cls(entry_hash, last_used_time, entry_size_256b_chunks)

    def __len__(self) -> int:
        return self.LEN
