# Copyright Colin Caine 2023. MIT License.

from collections import deque
from dataclasses import dataclass
from typing import Hashable

@dataclass(slots=True)
class S3FIFOItem:
    key: Hashable
    value: any
    freq: int = 0

class S3FIFO:
    """Cache calls to a function with S3FIFO.

    S3-FIFO is claimed to be a state-of-the art (2023) general-purpose cache.
    S3-FIFO claims these relative advantages over its competitors:

    - broad suitability
        - S3-FIFO has hit-rates competitive with the best state-of-the-art
          algorithm in each of a wide variety of real-world cache traces with
          different access-patterns
    - excellent hit-rates when a large proportion of cache keys are seen only
      once ("one-hit-wonders")
        - This is a common access pattern for second-level caches (e.g. a
          server-side cache of web content where the browser is the first-level
          cache).
    - memory use
        - S3-FIFO can outperform an LRU cache 5× bigger at small cache-sizes
    - runtime speed
        - FIFOs are simpler and faster than the double-linked-lists used in
          LRU-based caches

    See references below for the research.

    S3-FIFO was invented by Juncheng Yang, Ziyue Qiu, Yazhuo Zhang, Yao Yue and
    K V Rashimi.

    # Example use:

    ```python
    cache = S3Fifo(some_callable, maximum_number_of_cached_values)

    # Gets the return value of `some_callable(some_key)` or the saved
    # return value of an earlier call of `some_callable(some_key)`.
    value = cache.get(some_key)
    ```

    `get` and `some_callable` must accept a single value and that value must be
    usable as a `dict` key. If you want to key on multiple values then use a
    tuple or a hash of those of values as appropriate.

    # Performance testing

    I don't want to get the real world data, but supposedly the distribution of
    request keys is similar to a Zipf distribution, so I've tested with that.

    I compared S3FIFO with a simple FIFO cache and python's functools.lru_cache,
    neither of which are state of the art, but they are very easily available!

    In my tests, S3FIFO has a strong relative advantage over those simple
    competitors when the cache is very small and a modest advantage or no
    disadvantage when the cache is large. I am a hack and a fraud, so I didn't
    do significance testing.

    Run my benchmarks with `python3 tests.py`. You'll need scipy.

    # References

    In my opinion, the best resource for understanding S3-FIFO and why it works
    is this article (S3-FIFO corresponds to what they call QD-LP-FIFO):

    HOTOS 2023, FIFO can be Better than LRU: the Power of Lazy Promotion and
    Quick Demotion
        Juncheng Yang, Ziyue Qiu, Yazhuo Zhang, Yao Yue, K V Rashimi
        https://sigops.org/s/conferences/hotos/2023/papers/yang.pdf
        https://doi.org/10.1145/3593856.3595887

    Yang et al are publishing again at SOSP 2023 and that article may become
    the better reference. It will probably be publicly available sometime after
    October 23rd 2023. Search for "SOSP 2023, FIFO queues are all you need for
    cache eviction"

    Accessible explanations (warning: at the time of writing, the explanations
    include some mistakes, refer to the articles and implementations if you
    need the full picture):
        https://blog.jasony.me/system/cache/2023/08/01/s3fifo (animation!)
        https://s3fifo.com/

    S3-FIFO implementation in a cache simulation framework by Juncheng Yang. I
    believe that their performance claims are based on simulations run with
    libCacheSim on various real-world cache traces.
        https://github.com/1a1a11a/libCacheSim/blob/5fa68ef6902350aa9734398862bec7912d59f5e3/libCacheSim/cache/eviction/S3FIFO.c
    """
    """
    # Implementation

    See References for explanations of how the algorithm is supposed to work.
    This section explains how this implementation does work :)

    S3-FIFO consists of an index (a dict in this implementation) and three
    FIFOs (queues): small (S), main (M), and ghost (G).

    Cached entries are stored as Items, which have a key, value, and an integer
    we call `freq` that starts at 0. `value` will initially be func(key), where
    func is the callable argument given in the S3FIFO constructor, but can be
    set to None if the item is evicted from the cache.

    If a key is not in the index then we evict an item if the cache is full and
    then insert a new Item into the index and S.

    Items are only evicted or promoted from any queue if a new value is
    inserted when the cache is full (len(S)+len(M) == size).
     - S and M have target sizes of 10% and 90% of the specified cache size
       but can both grow to use the full cache so long as the combined length
       of S and M is less than the cache size.
     - The flexible size of S and M and this lazy eviction/promotion policy
       allows full use of the specified cache size for all access patterns
       and allows more time for each item to register a hit. The HotOS
       article calls this Lazy Promotion.

    When we need to evict, we evict from M if it is bigger than its target
    size, otherwise we try to evict from S (which can fail if it promotes a
    value to M instead). If S promotes then we loop, which will end up with us
    evicting from M. Either way, we evict one item. This loop is in
    ensure_free().
      - evictM() chooses an item to evict from the main FIFO
          - Eviction strategy is FIFO-Reinsertion with CLOCK-2
          - CLOCK-2 is a 2-bit clock for each item in the cache. On each
            cache-hit the clock is incremented if it is less than 3. We use
            item.freq as the clock value.
          - FIFO-Reinsertion: we pop an item and if its clock is > 0 it is
            pushed to the other end of the queue with clock reduced by 1. We
            keep trying until we see an item with clock == 0, then we evict
            that item.
          - Evicting an item means deleting it from the index, and setting its
            value to None (allows it to be garbage collected even if ghost FIFO
            retains a referece to it)
      - evictS() either promotes items to the main FIFO if they have been
        accessed at least once or demotes a single item to the ghost FIFO if
        they have not been accessed. Demotion to ghost counts as an eviction.
          - Promoted items have their clock reset to 0 and are enqueued in M.
          - Demoted items are not counted against our cache size because we set
            their value=None to allow garbage collection. We also set freq = -1
            so that we can identify them.
          - If an item is demoted and the ghost FIFO is free, then the ghost
            FIFO will pop its last item. If the popped item is not also in M,
            then it is deleted from the index. If item.freq < 0 then item is
            not in M.

    When we have a cache-hit we check if the hit item is in ghost FIFO:
      - if item.freq < 0, then item is in ghost GIFO.
          - recalculate the value: item.value = func(item.key)
          - promote into M by setting item.freq = 0 and enqueueing
          - no need to touch the ghost FIFO
      - else: increase the freq by 1, up to a maximum of 3 (2-bit clock)

    Because S is usually small and is the queue that new values are inserted
    into, items in it are eligible for eviction sooner than the average item in
    M. This preferential eviction of newer, unrepeated items is called Quick
    Demotion in the article. The ghost FIFO compensates for quick demotion by
    allowing values in it to skip straight to the larger main FIFO if they
    were evicted from S recently enough to still be in the ghost FIFO.
    """

    def __init__(self, func, max_num_cached):
        assert max_num_cached >= 10
        self.func = func
        target_len_s = max_num_cached // 10
        self.target_len_m = max_num_cached - target_len_s
        self.maxlen = target_len_s + self.target_len_m

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
                # Cache miss, item in G.
                # (Items entering G have freq set to -1)
                self.hit_ghosts += 1
                self.misses += 1

                # Re-cache the value and reset freq (import to do this before
                # ensure_free!)
                item.value = self.func(key)
                item.freq = 0

                # Add to M.
                self.ensure_free()
                self.insertM(item)

                # We don't need to delete from G, that will happen
                # automatically as we add values to G.
            else:
                # Cache hit! Update freq.
                self.hits += 1
                item.freq = min(item.freq + 1, 3)
        else:
            # Cache miss, unseen or forgotten key
            self.misses += 1

            # Calculate value and store in hash table.
            value = self.func(key)
            item = S3FIFOItem(key, value)
            self.table[key] = item

            # Insert into small fifo.
            self.ensure_free()
            self.insertS(item)

        return item.value

    def insertM(self, item):
        item.freq = 0
        self.M.appendleft(item)

    def insertS(self, item):
        self.S.appendleft(item)

    def insertG(self, new_item):
        # Evict an item if G is full. Items that have not been adopted into
        # another queue are completely removed from the cache.
        if len(self.G) == self.target_len_m:
            tail_item = self.G.pop()
            if tail_item.freq < 0:
                del self.table[tail_item.key]

        # Drop our reference to the value, possibly allowing it to be garbage
        # collected.
        new_item.value = None
        new_item.freq = -1
        self.G.appendleft(new_item)

    def ensure_free(self):
        "Ensure there is at least one location free for a new item"
        while len(self.S) + len(self.M) >= self.maxlen:
            # The `or` isn't required because we're working with integers, but
            # there's no harm and you need it if you want to adapt this code to
            # sum sizes rather than count number of cached values.
            if len(self.M) >= self.target_len_m or len(self.S) == 0:
                self.evictM()
            else:
                # We need the outer while loop because if every item in S is
                # eligible for promotion to M, then evictS() will not evict
                # anything to G and we will need to call evictM().
                self.evictS()

    def evictM(self):
        # Evict something, completely removing it from the cache. This will
        # always eventually evict one item because reinserted items have their
        # frequency reduced.
        while len(self.M) > 0:
            tail_item = self.M.pop()
            if tail_item.freq > 0:
                # Reinsert
                tail_item.freq -= 1
                self.M.appendleft(tail_item)
            else:
                # Evict
                # item may still be in G, set value = None to allow its value
                # to be garbage collected.
                tail_item.value = None
                del self.table[tail_item.key]
                return
        assert False, "Unreachable!"

    def evictS(self):
        # Promote items into M until we find an item we can demote to G or run
        # out of items.
        while len(self.S) > 0:
            # Move the tail item to another queue.
            tail_item = self.S.pop()
            if tail_item.freq > 0:
                self.insertM(tail_item)
            else:
                self.insertG(tail_item)
                return
