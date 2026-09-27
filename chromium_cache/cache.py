#!/usr/bin/env python3
from typing import Generator
from pathlib import Path
from .entry import EntryFile_0
from .index import SimpleIndex

__all__ = ["DiskCache"]


class DiskCache:
    def __init__(self, dir: str | Path) -> None:
        self.__load(Path(dir))

    def __load(self, dir: Path) -> None:
        self.path = dir
        self.index = SimpleIndex.load(dir)

    def __iter__(self) -> Generator[EntryFile_0, None, None]:
        for item in dir.iterdir():
            if not item.is_file():
                continue
            if len(item.name) != 18:
                continue
            if not item.name.endswith("_0"):
                continue
            yield EntryFile_0(item)
