# Explore Cache Data of Chromium Browser

Tested on Chromium 76.0.3809.100.

```py
>>> from chromium_cache import CacheIndex
>>> idx = CacheIndex('path/to/cache/directory')
>>> [entry.url for entry in idx]
['http://www.example.com/foo.jpg', ...]
>>> entry = idx['http://www.example.com/foo.jpg']
>>> entry.url
'http://www.example.com/foo.jpg'
>>> entry.data
<memory at 0x7f03c8c1d648>
```
