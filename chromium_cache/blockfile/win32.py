#!/usr/bin/env python3
import ctypes
import msvcrt
import os
from enum import IntFlag
from ctypes import wintypes

__all__ = ["ShareMode", "win32_make_opener"]

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
CreateFileW.restype = wintypes.HANDLE
CloseHandle = kernel32.CloseHandle


class ShareMode(IntFlag):
    READ = 0x1
    WRITE = 0x2
    DELETE = 0x4


GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
CREATE_NEW, CREATE_ALWAYS, OPEN_EXISTING, OPEN_ALWAYS, TRUNCATE_EXISTING = 1, 2, 3, 4, 5
FILE_ATTRIBUTE_NORMAL = 0x80
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


def win32_make_opener(share=ShareMode.READ | ShareMode.WRITE | ShareMode.DELETE):
    def opener(path, flags):
        # permissions
        if flags & os.O_RDWR:
            access = GENERIC_READ | GENERIC_WRITE
        elif flags & os.O_WRONLY:
            access = GENERIC_WRITE
        else:
            access = GENERIC_READ

        # creation methods
        if flags & os.O_CREAT and flags & os.O_EXCL:
            disp = CREATE_NEW
        elif flags & os.O_CREAT and flags & os.O_TRUNC:
            disp = CREATE_ALWAYS
        elif flags & os.O_CREAT:
            disp = OPEN_ALWAYS
        elif flags & os.O_TRUNC:
            disp = TRUNCATE_EXISTING
        else:
            disp = OPEN_EXISTING

        h = CreateFileW(
            os.fsdecode(path),
            access,
            share.value,
            None,
            disp,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if h == INVALID_HANDLE_VALUE:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return msvcrt.open_osfhandle(
                h, flags & (os.O_APPEND | os.O_RDONLY | os.O_TEXT)
            )
        except Exception:
            CloseHandle(h)
            raise

    return opener
