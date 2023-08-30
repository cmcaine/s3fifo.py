from collections import deque
from dataclasses import dataclass
from typing import Hashable

from s3fifo import S3FIFO

@dataclass(slots=True)
class S3FIFOItem:
    key: Hashable
    value: any
    freq: int = 0

# These next two are Like S3FIFO, but S3FIFO3 removes a single item at a time from
# evictS() and S3FIFO4 promotes consecutive items if possible, but stops when
# it can't promote any more
#
# From my limited testing with no statistics:
#     S3FIFO == S3FIFO3
#     S3FIFO > S3FIFO4 > EagerEvictionS3FIFO
#
# 2, 3 and 4 have different behaviour when size(M) <= maxlen_m and the next N
# values from S are promotable to M (we'll call them s0, ..., sN-1) and the value
# after (sN) is not.
#
#  - S3FIFO:
#     - s0..sN-1 are promoted to M and set freq=0
#       reset clocks
#     - sN is evicted
#     - if M is now full, then on the nect eviction a value from M will be
#       evicted, else sN+1 will be promoted or evicted.
#  - S3FIFO3:
#     - s0 is promoted and sets freq=0
#     - a value from M is evicted
#     - the currently unpromoteable sN has more time to collect a hit
#     - if M is now full, then on the next eviction a value from M will be evicted, else sN
#  - S3FIFO4:
#     - s0..sN-1 are promoted to M and set freq=0
#     - otherwise same as S3FIFO3.
class S3FIFO3(S3FIFO):
    def evictS(self):
        if len(self.S) > 0:
            # Move the tail item to another queue.
            tail_item = self.S.pop()
            if tail_item.freq > 0:
                self.insertM(tail_item)
            else:
                self.insertG(tail_item)

class S3FIFO4(S3FIFO):
    def evictS(self):
        if len(self.S) > 0:
            tail_item = self.S.pop()
            # Promote all eligible items to M
            if tail_item.freq > 0:
                self.insertM(tail_item)
                while len(self.S) > 0:
                    tail_item = self.S.pop()
                    self.insertM(tail_item)
            # Or, if the next item is not promotable, evict it.
            else:
                self.insertG(tail_item)

class EagerEvictionS3FIFO:
    # A bad version of S3FIFO.

    # Public

    def __init__(self, func, max_num_cached):
        assert max_num_cached >= 10
        self.func = func
        self.maxlen_s = max_num_cached // 10
        self.maxlen_m = max_num_cached - self.maxlen_s

        # Stats
        self.hits = self.hit_ghosts = self.misses = 0

        # hashtable of key => Item for each item in S, M, G
        self.table = {}
        # FIFOs of Items
        self.S = deque()
        self.M = deque()
        self.G = deque()

    def get(self, key):
        """Return a (possibly cached) return value of `func(key)`."""
        item = None
        if key in self.table:
            item = self.table[key]
            if item.freq < 0:
                self.hit_ghosts += 1
                self.misses += 1
                item.value = self.func(key)
                self.insertM(item)
            else:
                self.hits += 1
                item.freq = min(item.freq + 1, 3)
        else:
            self.misses += 1
            value = self.func(key)
            item = S3FIFOItem(key, value)
            self.table[key] = item
            self.insertS(item)
        return item.value

    # Private

    def insertM(self, new_item):
        # Evict something if necessary, completely removing it from the cache.
        # If M is full then this will always eventually evict one item because
        # reinserted items have their frequency reduced.
        while (len(self.M) == self.maxlen_m):
            tail_item = self.M.pop()
            if tail_item.freq > 0:
                tail_item.freq -= 1
                self.M.appendleft(tail_item)
            else:
                del self.table[tail_item.key]

        new_item.freq = 0
        self.M.appendleft(new_item)

    def insertS(self, new_item):
        # If S is full, move the tail item to another queue.
        if (len(self.S) == self.maxlen_s):
            tail_item = self.S.pop()
            if tail_item.freq > 0:
                self.insertM(tail_item)
            else:
                self.insertG(tail_item)

        new_item.freq = 0
        self.S.appendleft(new_item)

    def insertG(self, new_item):
        # Evict an item if G is full. Items that have not been adopted into
        # another queue are completely removed from the cache.
        if len(self.G) == self.maxlen_m:
            tail_item = self.G.pop()
            if tail_item.freq < 0:
                del self.table[tail_item.key]

        # Drop our reference to the value, possibly allowing it to be garbage
        # collected.
        new_item.value = None
        new_item.freq = -1
        self.G.appendleft(new_item)


class FIFO:
    def __init__(self, func, size):
        self.func = func
        self.table = {}
        self.fifo = deque()
        self.maxlen = size
        self.hits = self.misses = 0

    def get(self, key):
        if key in self.table:
            self.hits += 1
            return self.table[key]
        else:
            self.misses += 1
            if len(self.fifo) == self.maxlen:
                k = self.fifo.pop()
                del self.table[k]
            val = self.func(key)
            self.table[key] = val
            self.fifo.appendleft(key)
            return val

import functools

class LRU:
    def __init__(self, func, size):
        @functools.lru_cache(size)
        def get(key):
            return func(key)
        self.get = get

    @property
    def hits(self):
        return self.get.cache_info().hits

    @property
    def misses(self):
        return self.get.cache_info().misses
