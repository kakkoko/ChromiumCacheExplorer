from io import RawIOBase
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

from .block import BlockFileHeader
from .utils import BinaryReader, custom_open
from .blockview import BlockView

__all__ = ["CacheAddress", "FileType", "new_address"]


class FileType(Enum):
    EXTERNAL = 0
    """Store the data in an external file 'f_XXXXXX'"""
    RANKINGS = 1
    """Store the data in a block file 'data_0 (with a block size of 36B) or its successors"""
    BLOCK_256 = 2
    """Store the data in a block file 'data_1 (with a block size of 256B) or its successors"""
    BLOCK_1K = 3
    """Store the data in a block file 'data_2 (with a block size of 1KiB) or its successors"""
    BLOCK_4K = 4
    """Store the data in a block file 'data_3 (with a block size of 4KiB) or its successors"""
    BLOCK_FILES = 5
    """Reserved; currently not in use"""
    BLOCK_ENTRIES = 6
    """Reserved; currently not in use"""
    BLOCK_EVICTED = 7
    """Reserved; currently not in use"""


BLOCK_SIZE_OF: dict[FileType, int] = {
    FileType.RANKINGS: 36,
    FileType.BLOCK_256: 256,
    FileType.BLOCK_1K: 1024,
    FileType.BLOCK_4K: 4096,
    FileType.BLOCK_FILES: 8,
    FileType.BLOCK_ENTRIES: 104,
    FileType.BLOCK_EVICTED: 48,
}
"""A dictionary object for determining the block size of a block file.
"""


class CacheAddress(ABC):
    __slots__ = ()

    def __bool__(self) -> bool:
        return self.initialized

    @property
    @abstractmethod
    def initialized(self) -> bool: ...

    @property
    @abstractmethod
    def value(self) -> int: ...

    @property
    @abstractmethod
    def dir(self) -> Path: ...

    @property
    @abstractmethod
    def type(self) -> FileType: ...

    @property
    @abstractmethod
    def path(self) -> Path: ...

    @property
    @abstractmethod
    def filename(self) -> str: ...

    @property
    @abstractmethod
    def offset(self) -> int: ...

    @property
    @abstractmethod
    def size(self) -> int: ...

    @abstractmethod
    def open(self) -> BinaryReader: ...


class UninitializedAddress(CacheAddress):
    """A cache address value indicating an uninitialized or invalid address."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    @property
    def initialized(self) -> bool:
        return False

    @property
    def value(self) -> int:
        return 0

    @property
    def dir(self) -> Path:
        raise ValueError()

    @property
    def type(self) -> FileType:
        raise ValueError()

    @property
    def path(self) -> Path:
        raise ValueError()

    @property
    def filename(self) -> str:
        raise ValueError()

    @property
    def offset(self) -> int:
        raise ValueError()

    @property
    def size(self) -> int:
        raise ValueError()

    def open(self) -> BinaryReader:
        raise ValueError()


class ExternalAddress(CacheAddress):
    """A cache address value that refers to data stored in a separate external file."""

    def __init__(self, dir: Path, file_number: int) -> None:
        self.__dir = dir
        self.file_number = file_number

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.dir!r}, {self.file_number:#08x})"

    @property
    def initialized(self) -> bool:
        return True

    @property
    def value(self) -> int:
        return 0x8000_0000 | (FileType.EXTERNAL.value << 28) | self.file_number

    @property
    def dir(self) -> Path:
        return self.__dir

    @property
    def type(self) -> FileType:
        return FileType.EXTERNAL

    @property
    def path(self) -> Path:
        return self.dir / self.filename

    @property
    def filename(self) -> str:
        return f"f_{self.file_number:06x}"

    @property
    def offset(self) -> int:
        return 0

    @property
    def size(self) -> int:
        return self.path.stat().st_size

    def open(self) -> BinaryReader:
        return custom_open(self.path)


class BlockAddress(CacheAddress):
    """A cache address value that points to data stored in a specific block of a block file."""

    def __init__(
        self,
        dir: Path,
        type: FileType,
        num_blocks: int,
        file_selector: int,
        start_block: int,
    ) -> None:
        if type == FileType.EXTERNAL:
            raise ValueError()
        self.__dir = dir
        self.__type = type
        self.num_blocks = num_blocks
        self.file_selector = file_selector
        self.start_block = start_block

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.dir!r}, {self.type!r}, {self.num_blocks!r}, {self.file_selector!r}, {self.start_block!r})"

    @property
    def initialized(self) -> bool:
        return True

    @property
    def value(self) -> int:
        return (
            0x8000_0000
            | (self.type.value << 28)
            | ((self.num_blocks - 1) << 24)
            | (self.file_selector << 16)
            | self.start_block
        )

    @property
    def dir(self) -> Path:
        return self.__dir

    @property
    def type(self) -> FileType:
        return self.__type

    @property
    def path(self) -> Path:
        return self.dir / self.filename

    @property
    def filename(self) -> str:
        return f"data_{self.file_selector}"

    @property
    def offset(self) -> int:
        return BlockFileHeader.SIZE_BYTES + BLOCK_SIZE_OF[self.type] * self.start_block

    @property
    def size(self) -> int:
        return BLOCK_SIZE_OF[self.type] * self.num_blocks

    def open(self) -> BinaryReader:
        return BlockView(self.path, self.offset, self.size)


def new_address(dir: Path, value: int) -> CacheAddress:
    if value < 0 or value > 0xFFFF_FFFF:
        raise ValueError()
    if (value >> 31) == 0:
        return UninitializedAddress()
    type = FileType((value >> 28) & 0b111)
    if type == FileType.EXTERNAL:
        return ExternalAddress(dir, value & 0x0FFF_FFFF)
    if type in (
        FileType.RANKINGS,
        FileType.BLOCK_256,
        FileType.BLOCK_1K,
        FileType.BLOCK_4K,
    ):
        return BlockAddress(
            dir,
            type,
            ((value >> 24) & 0b11) + 1,
            (value >> 16) & 0xFF,
            value & 0xFFFF,
        )
    raise ValueError()
