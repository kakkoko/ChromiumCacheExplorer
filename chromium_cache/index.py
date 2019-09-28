#!/usr/bin/env python3
from typing import Union, Any, Iterable
from pathlib import Path
import sys
import struct
import binascii
import hashlib
from .entry import CacheEntry

if sys.version_info < (3, 6):
    raise ValueError('unsupported Python version; requires 3.6 or later')

__all__ = ['CacheIndex']

# ref: disk_cache::kSimpleVersion
_SUPPORTED_VERSION = 9


class CacheIndex:
    def __init__(self, *args, **kwds) -> None:
        self.base = None  # type: Optional[Path]
        self.hashes = set()  # type: Set[int]
        self.version = _SUPPORTED_VERSION
        if args or kwds:
            self.load(*args, **kwds)

    def load(self, dir: Union[str, Path], *, strict: bool = False) -> None:
        cache_dir = Path(dir)
        if not cache_dir.is_dir():
            raise ValueError('cache directory not found')

        # ref: disk_cache::SimpleIndexFile::kIndexFileName,
        #      disk_cache::SimpleIndexFile::kIndexDirectory
        index_file = cache_dir / 'index-dir' / 'the-real-index'
        if not index_file.is_file():
            raise ValueError('cache index file not found')

        with index_file.open('rb') as src:
            data = memoryview(src.read())
        # ref: base::Pickle::headerT,
        #      disk_cache::SimpleIndexFile::Deserialize
        payload_size, crc = struct.unpack_from('=LL', data)
        payload = data[8:]
        if len(payload) != payload_size:
            raise ValueError('invalid payload size')
        if binascii.crc32(payload) & 0xffffffff != crc:
            raise ValueError('crc32 mismatch')

        # ref: disk_cache::SimpleIndexFile::IndexMetadata::Deserialize
        magic_number, version, entry_count, cache_size = struct.unpack_from(
            '=QLQQ', payload)
        if version >= 7:
            reason = struct.unpack_from('=L', payload, 28)
            payload = payload[32:]
        else:
            reason = None
            payload = payload[28:]

        if magic_number != 0x656e74657220796f:
            raise ValueError('magic number mismatch')
        if strict and version > _SUPPORTED_VERSION:
            raise ValueError('unsupported file version')

        hashes = set()  # type: Set[int]
        # ref: disk_cache::SimpleIndexFile::Deserialize
        while len(hashes) < entry_count:
            hash, = struct.unpack_from('=Q', payload)
            hashes.add(hash)
            payload = payload[24:]

        self.base = cache_dir
        self.hashes = hashes
        self.version = version

    @classmethod
    def hash(cls, url: str) -> int:
        # ref: disk_cache::simple_util::GetEntryHashKey
        digest = hashlib.sha1(url.encode()).digest()
        return struct.unpack('=Q', digest[:8])

    def __path(self, hash: int) -> Path:
        return self.base / f'{hash:08x}_0'

    def __len__(self) -> int:
        return len(self.hashes)

    def __contains__(self, key: Union[int, str]) -> bool:
        n = key if isinstance(key, int) else self.hash(key)
        return n in self.hashes

    def __getitem__(self, key: Union[int, str]) -> CacheEntry:
        n = key if isinstance(key, int) else self.hash(key)
        if n not in self.hashes:
            raise KeyError('unknown key')
        return CacheEntry(self.__path(n))

    def files(self) -> Iterable[Path]:
        yield from (self.__path(hash) for hash in self.hashes)

    def entries(self) -> Iterable[CacheEntry]:
        yield from (CacheEntry(self.__path(hash)) for hash in self.hashes)
