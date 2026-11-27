# Explore Cache Data of Chromium Browser

Tested on Chromium 158.0.8127.37.

```py
>>> import os
>>> from pathlib import Path
>>> from chromium_cache.blockfile import *
>>> cache = BlockFileCache(Path(os.getenv("APPDATA")) / "Local" / "Google" / "Chrome" / "User Data" / "Default" / "Cache" / "Cache_Data")
>>> [entry.url for entry in cache]
['http://www.example.com/foo.jpg', ...]
```

Each `entry` has:

* `creation_time: datetime`
* `available: bool`
    - `True` if `body` is available
* `url: str`
* `response_info: ResponseInfo`
    - Dictionary object
* `body: bytes`
* `content_encoding: bytes | None`
