from typing import ByteString, Iterable, ClassVar
from dataclasses import dataclass
from enum import Enum, IntFlag
from pathlib import Path
from datetime import datetime
import struct

from .address import CacheAddress, FileType, new_address
from .blockview import BlockView
from .decompress import DecompressingReader, create_decompressor, decompress_content
from .utils import BinaryReader, ReadableBuffer, key2url
from ..time import timestamp_from_microseconds
from ..hash import persistent_hash

__all__ = [
    "EntryFlags",
    "EntryStore",
    "ResponseFlags",
    "ResponseExtraFlags",
    "ResponseInfo",
]


class ResponseFlags(IntFlag):
    VERSION_MASK = 0xFF
    HAS_CERT = 0x100
    HAS_SECURITY_BITS = 0x200
    HAS_CERT_STATUS = 0x400
    HAS_VARY_DATA = 0x800
    TRUNCATED = 0x1000
    WAS_SPDY = 0x2000
    WAS_ALPN = 0x4000
    WAS_PROXY = 0x8000
    HAS_SSL_CONNECTION_STATUS = 0x1_0000
    HAS_ALPN_NEGOTIATED_PROTOCOL = 0x2_0000
    HAS_CONNECTION_INFO = 0x4_0000
    USE_SERVER_HTTP_AUTHENTICATION = 0x8_0000
    HAS_SIGNED_CERTIFICATE_TIMESTAMPS = 0x10_0000
    UNUSED_SINCE_PREFETCH = 0x20_0000
    HAS_KEY_EXCHANGE_GROUP = 0x40_0000
    PKP_BYPASSED = 0x80_0000
    HAS_STALENESS = 0x100_0000
    HAS_PEER_SIGNATURE_ALGORITHM = 0x200_0000
    RESTRICTED_PREFETCH = 0x400_0000
    HAS_DNS_ALIASES = 0x800_0000
    UNUSED_WAS_SINGLE_KEYED_CACHE_ENTRY_UNUSABLE = 0x1000_0000
    ENCRYPTED_CLIENT_HELLO = 0x2000_0000
    BROWSER_RUN_ID = 0x4000_0000
    HAS_EXTRA_FLAGS = 0x8000_0000


class ResponseExtraFlags(IntFlag):
    DID_USE_SHARED_DICTIONARY = 0x1
    HAS_PROXY_CHAIN = 0x2
    HAS_ORIGINAL_RESPONSE_TIME = 0x4
    HAS_ENCODED_BODY_SIZE = 0x8
    HAS_ZSTD_UNCOMPRESSED_BODY_SIZE = 0x10


class EntryState(Enum):
    NORMAL = 0
    EVICTED = 1
    DOOMED = 2


class EntryFlags(IntFlag):
    PARENT_ENTRY = 1
    CHILD_ENTRY = 2


@dataclass
class PickleHeader:
    SIZE_BYTES: ClassVar[int] = 36

    payload_size: int
    flags: ResponseFlags
    extra_flags: ResponseExtraFlags
    request_time: datetime
    response_time: datetime
    original_response_time: datetime

    @classmethod
    def unpack_from(cls, buffer: ReadableBuffer, offset: int = 0) -> "PickleHeader":
        values = struct.unpack_from("=Iiiqqq", buffer, offset)

        return cls(
            payload_size=values[0],
            flags=ResponseFlags(values[1]),
            extra_flags=ResponseExtraFlags(values[2]),
            request_time=timestamp_from_microseconds(values[3]),
            response_time=timestamp_from_microseconds(values[4]),
            original_response_time=timestamp_from_microseconds(values[5]),
        )

    @classmethod
    def read_from(cls, file: BinaryReader) -> "PickleHeader":
        data = file.read(cls.SIZE_BYTES)
        assert data is not None
        return cls.unpack_from(data)

    @property
    def version(self) -> int:
        return self.flags & ResponseFlags.VERSION_MASK


@dataclass
class Stream:
    size: int
    addr: CacheAddress
    content_encoding: bytes | None = None

    def __bool__(self) -> bool:
        return self.addr.initialized

    def open(self) -> BinaryReader:
        view = BlockView(self.addr.path, offset=self.addr.offset, size=self.size)
        if self.content_encoding:
            return DecompressingReader(view, create_decompressor(self.content_encoding))
        return view

    def readall(self) -> bytes:
        with BlockView(self.addr.path, offset=self.addr.offset, size=self.size) as f:
            data = f.read()
        if self.content_encoding:
            return decompress_content(self.content_encoding, data)
        return data


class ResponseInfo(dict):
    __slots__ = ("header",)

    def __init__(
        self,
        header: PickleHeader,
        items: Iterable[tuple[ReadableBuffer, ReadableBuffer]],
    ) -> None:
        self.header = header
        super().__init__(items)

    @staticmethod
    def decode_response_header(
        data: bytes,
    ) -> Iterable[tuple[bytes, bytes]]:
        for line in data.split(b"\x00")[1:-2]:
            key, value = line.split(b":", maxsplit=1)
            yield key, value

    @classmethod
    def from_stream(cls, stream: Stream) -> "ResponseInfo":
        with stream.open() as f:
            header = PickleHeader.read_from(f)
            raw_size = f.read(4) or b""
            (size,) = struct.unpack("=i", raw_size)
            data = f.read(size) or b""
        if not data.endswith(b"\x00\x00"):
            raise ValueError()
        return ResponseInfo(header, cls.decode_response_header(data))


@dataclass
class EntryStore:
    SIZE_BYTES: ClassVar[int] = 256

    hash: int
    next: CacheAddress
    rankings_node: CacheAddress
    reuse_count: int
    refetch_count: int
    state: EntryState
    creation_time: datetime
    key_len: int
    long_key: CacheAddress
    streams: list[Stream]
    flags: EntryFlags
    self_hash: int
    key: bytes

    address: CacheAddress
    _response_info: ResponseInfo | None = None

    def __post_init__(self) -> None:
        if self.streams[0] and self.streams[1]:
            self.streams[1].content_encoding = self.content_encoding

    @classmethod
    def load(cls, addr: CacheAddress) -> "EntryStore":
        with addr.open() as file:
            data = file.read(cls.SIZE_BYTES) or b""
            values = struct.unpack("=IIIiiiQiI4i4II4iI160s", data)

            self_hash: int = values[22]
            if self_hash != persistent_hash(data[0:92]):
                raise ValueError()

            ranking_node = new_address(addr.dir, values[2])
            key_len = values[7]
            if key_len > 0 and not ranking_node:
                raise ValueError()

            long_key = new_address(addr.dir, values[8])
            if key_len <= 927 and long_key:
                raise ValueError()
            if key_len > 927 and not long_key:
                raise ValueError()

            streams = [
                Stream(data_size, new_address(addr.dir, data_addr))
                for data_size, data_addr in zip(values[9:13], values[13:17])
            ]
            for stream in streams:
                if stream.size == 0:
                    continue
                if stream.size <= 16384 and stream.addr.type == FileType.EXTERNAL:
                    raise ValueError()
                if stream.size > 16384 and stream.addr.type != FileType.EXTERNAL:
                    raise ValueError()

            key: bytes = values[23]
            if key_len < 160:
                key = key[: key_len + 1]
            elif key_len <= 927:
                key += file.read(key_len + 1 - 160) or b""
                if len(key) != key_len + 1:
                    raise ValueError()
            else:
                with long_key.open() as key_file:
                    key = key_file.read(key_len + 1) or b""
            if key[key_len] != 0:
                raise ValueError()
            key = key[:-1]

        return cls(
            hash=values[0],
            next=new_address(addr.dir, values[1]),
            rankings_node=ranking_node,
            reuse_count=values[3],
            refetch_count=values[4],
            state=EntryState(values[5]),
            creation_time=timestamp_from_microseconds(values[6]),
            key_len=key_len,
            long_key=new_address(addr.dir, values[8]),
            streams=streams,
            flags=EntryFlags(values[17]),
            self_hash=values[22],
            key=key,
            address=addr,
        )

    @property
    def dir(self) -> Path:
        return self.address.dir

    @property
    def available(self) -> bool:
        return self.state == EntryState.NORMAL

    @property
    def url(self) -> str:
        return key2url(self.key)

    @property
    def response_info(self) -> ResponseInfo:
        if self._response_info is None:
            self._response_info = ResponseInfo.from_stream(self.streams[0])
        return self._response_info

    @property
    def body(self) -> bytes:
        return self.streams[1].readall()

    @property
    def content_encoding(self) -> bytes | None:
        return self.response_info.get(b"content-encoding")
