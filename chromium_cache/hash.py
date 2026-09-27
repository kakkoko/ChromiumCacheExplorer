#!/usr/bin/env python3
from typing import ByteString
from hashlib import sha1, sha256
import struct

__all__ = ["persistent_hash", "sha1_hash", "sha256_hash"]

M32 = 0xFFFFFFFF


def persistent_hash(data: ByteString) -> int:
    n = len(data)
    if n == 0:
        return 0
    h, rem, i = n, n & 3, 0
    s8 = lambda b: b - 256 if b >= 128 else b
    for _ in range(n >> 2):
        h = (h + (data[i] | data[i + 1] << 8)) & M32
        t = (((data[i + 2] | data[i + 3] << 8) << 11) & M32) ^ h
        h = ((h << 16) & M32) ^ t
        i += 4
        h = (h + (h >> 11)) & M32
    if rem == 3:
        h = (h + (data[i] | data[i + 1] << 8)) & M32
        h ^= (h << 16) & M32
        h ^= (s8(data[i + 2]) << 18) & M32
        h = (h + (h >> 11)) & M32
    elif rem == 2:
        h = (h + (data[i] | data[i + 1] << 8)) & M32
        h ^= (h << 11) & M32
        h = (h + (h >> 17)) & M32
    elif rem == 1:
        h = (h + s8(data[i])) & M32
        h ^= (h << 10) & M32
        h = (h + (h >> 1)) & M32
    for sh_l, sh_r in ((3, 5), (4, 17), (25, 6)):
        h ^= (h << sh_l) & M32
        h = (h + (h >> sh_r)) & M32
    return h


def sha1_hash(data: ByteString) -> int:
    return struct.unpack_from("=Q", sha1(data).digest())


def sha256_hash(data: ByteString) -> bytes:
    return sha256(data).digest()
