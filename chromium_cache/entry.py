#!/usr/bin/env python3
from typing import Union
from pathlib import Path
import struct
import binascii
import hashlib

__all__ = ['CacheEntry']

_FLAG_HAS_CRC32 = 0x01
_FLAG_HAS_KEY_SHA256 = 0x02


class CacheEntry:
    def __init__(self, file: Union[str, Path]) -> None:
        cache_file = Path(file)
        with cache_file.open('rb') as src:
            data = memoryview(src.read())

        magic_number, version, key_length, key_hash, padding = struct.unpack(
            '=QLLLL', data[:24])
        data = data[24:]
        if magic_number != 0xfcfb6d1ba7725c30:
            raise ValueError('magic number mismatch')

        key = data[:key_length]
        data = data[key_length:]

        magic_number, flags, crc32, stream_size, padding = struct.unpack(
            '=QLLLL', data[-24:])
        data = data[:-24]
        if magic_number != 0xf4fa6f45970d41d8:
            raise ValueError('magic number mismatch')

        sha256 = None
        if flags & _FLAG_HAS_KEY_SHA256:
            data, sha256 = data[:-32], data[-32:]

        if len(data) != stream_size:
            data = data[:-stream_size]

            magic_number, flags, crc32, stream_size, padding = struct.unpack(
                '=QLLLL', data[-24:])
            data = data[:-24]
            if magic_number != 0xf4fa6f45970d41d8:
                raise ValueError('magic number mismatch')

            sha256 = None
            if flags & _FLAG_HAS_KEY_SHA256:
                data, sha256 = data[:-32], data[-32:]

            if len(data) != stream_size:
                raise ValueError('invalid stream size')

        if flags & _FLAG_HAS_CRC32 and binascii.crc32(data) != crc32:
            raise ValueError('crc32 mismatch')
        if sha256 and hashlib.sha256(data).digest() != sha256:
            raise ValueError('sha256 mismatch')

        self.file = cache_file
        self.url = key.tobytes().decode()
        self.data = data
