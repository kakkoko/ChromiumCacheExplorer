from __future__ import annotations
from typing import Iterator
from types import TracebackType
from pathlib import Path

from .entry import EntryStore
from .index import IndexFile

__all__ = ["BlockFileCache"]


class BlockFileCache:
    def __init__(self, dir: str | Path) -> None:
        self.dir = Path(dir)
        self.index = IndexFile(self.dir / "index")

    @property
    def closed(self) -> bool:
        return self.index.closed

    def close(self) -> None:
        self.index.close()

    def __enter__(self) -> "BlockFileCache":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        self.index.close()

    def __iter__(self) -> Iterator[EntryStore]:
        for head in self.index:
            addr, seen = head, set()
            while addr and addr not in seen:
                seen.add(addr)
                entry = EntryStore.load(addr)
                if entry.available:
                    yield entry
                addr = entry.next
