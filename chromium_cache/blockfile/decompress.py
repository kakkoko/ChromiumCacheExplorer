from __future__ import annotations
from typing import Callable
from abc import ABC, abstractmethod
from io import RawIOBase
import zlib

from .utils import BinaryReader, ReadableBuffer, WriteableBuffer

__all__ = [
    "DecompressingReader",
    "StreamDecompressor",
    "create_decompressor",
    "decompress_content",
]


class StreamDecompressor(ABC):
    __slots__ = ()

    @abstractmethod
    def decompress(self, data: ReadableBuffer) -> ReadableBuffer: ...

    @property
    @abstractmethod
    def eof(self) -> bool: ...


class GZipDecompressor(StreamDecompressor):
    def __init__(self) -> None:
        self.decobj = zlib.decompressobj(16 + zlib.MAX_WBITS)

    def decompress(self, data: ReadableBuffer) -> ReadableBuffer:
        return self.decobj.decompress(data)

    @property
    def eof(self) -> bool:
        return self.decobj.eof


class DeflateDecompressor(StreamDecompressor):
    def __init__(self) -> None:
        self.decobj = zlib.decompressobj()

    def decompress(self, data: ReadableBuffer) -> ReadableBuffer:
        return self.decobj.decompress(data)

    @property
    def eof(self) -> bool:
        return self.decobj.eof


def gzip_decompressor(data: ReadableBuffer) -> bytes:
    return zlib.decompress(data, 16 + zlib.MAX_WBITS)


def deflate_decompressor(data: ReadableBuffer) -> bytes:
    return zlib.decompress(data)


_ONE_SHOT_DECOMPRESSORS: dict[bytes, Callable[[ReadableBuffer], bytes]] = {
    b"gzip": gzip_decompressor,
    # b"compress": None,
    b"deflate": deflate_decompressor,
    # b"br": None,
    # b"zstd": None,
    # b"dcb": None,
    # b"dcz": None,
}

_STREAM_DECOMPRESSORS: dict[bytes, type] = {
    b"gzip": GZipDecompressor,
    # b"compress": None,
    b"deflate": DeflateDecompressor,
    # b"br": None,
    # b"zstd": None,
    # b"dcb": None,
    # b"dcz": None,
}

try:
    import brotli

    class BrotliDecompressor(StreamDecompressor):
        def __init__(self) -> None:
            self.decobj = brotli.Decompressor()

        def decompress(self, data: ReadableBuffer) -> ReadableBuffer:
            return self.decobj.process(data)

        @property
        def eof(self) -> bool:
            return self.decobj.is_finished

    _ONE_SHOT_DECOMPRESSORS[b"br"] = brotli.decompress
    _STREAM_DECOMPRESSORS[b"br"] = BrotliDecompressor
except ImportError:
    pass

try:
    import zstandard

    class ZstdDecompressor(StreamDecompressor):
        def __init__(self) -> None:
            self.ctx = zstandard.ZstdDecompressor()
            self.decobj = self.ctx.decompressobj()

        def decompress(self, data: ReadableBuffer) -> ReadableBuffer:
            return self.decobj.decompress(data)

        @property
        def eof(self) -> bool:
            return self.decobj.eof

    _ONE_SHOT_DECOMPRESSORS[b"zstd"] = zstandard.decompress
    _STREAM_DECOMPRESSORS[b"zstd"] = ZstdDecompressor
except ImportError:
    pass


class DecompressingReader(RawIOBase):
    def __init__(
        self, raw: BinaryReader, decompressor: StreamDecompressor, read_unit: int = 1024
    ) -> None:
        self.raw = raw
        self.dec = decompressor
        self.read_unit = read_unit
        self.offset = 0
        self.data: ReadableBuffer | None = None

    def readinto(self, b: WriteableBuffer) -> int:  # type: ignore
        while not self.data:
            compressed = self.raw.read(self.read_unit)
            if not compressed:
                assert self.dec.eof
                return 0
            decompressed = self.dec.decompress(compressed)
            if decompressed:
                self.data = decompressed
                self.offset = 0
        usable = len(self.data) - self.offset
        size = min(len(b), usable)
        b[0:size] = self.data[self.offset : self.offset + size]
        self.offset += size
        if len(self.data) <= self.offset:
            self.data = None
        return size


def decompress_content(content_encoding: bytes, contents: ReadableBuffer) -> bytes:
    return _ONE_SHOT_DECOMPRESSORS[content_encoding](contents)


def create_decompressor(content_encoding: bytes) -> StreamDecompressor:
    return _STREAM_DECOMPRESSORS[content_encoding]()
