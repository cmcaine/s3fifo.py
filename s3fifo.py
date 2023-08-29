from collections import deque

class S3FIFO:
    """Cache calls to a function with S3FIFO.

    # Example use:

    ```python
    cache = S3Fifo(some_callable, maximum_number_of_cached_values)

    # Gets the return value of `some_callable(some_key)` or the saved
    # return value of an earlier call of `some_callable(some_key)`.
    value = cache.get(some_key)
    ```

    `get` and `some_callable` must accept a single value and that value must
    be usable as a `dict` key.

    # Performance

    S3FIFO allegedly performs well on many real-world datasets, and is adapted
    for the common case that a large proportion of requests are unique within
    some reasonable time frame.

    I don't want to get the real world data, but supposedly the distribution of
    request keys is similar to a Zipf distribution, so I've tested with that.
    I compared S3FIFO with a simple FIFO and python's functools.lru_cache,
    neither of which are state of the art.

    In my tests, S3FIFO has a strong relative advantage when the cache is very
    small and a slight relative disadvantage when the cache is large.


    Reference: https://blog.jasony.me/system/cache/2023/08/01/s3fifo
    """

    class Item:
        def __init__(self, key, value):
            self.key = key
            self.value = value
            self.freq = 0

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
            item = S3FIFO.Item(key, value)
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

def tests():
    # Simple test

    f = lambda x: 2*x
    cache = S3FIFO(f, 20)
    assert [cache.get(x) for x in range(30)] == [f(x) for x in range(30)]

    # Performance comparisons

    from collections import Counter

    kinds = (S3FIFO, LRU, FIFO)

    def print_input_stats(name, inputs):
        N = len(inputs)
        ctr = Counter(inputs)
        ohw = 100*list(ctr.values()).count(1) / N
        width = 0
        acc = 0
        for freq in sorted(ctr.values(), reverse=True):
            acc += freq
            width += 1
            if acc >= N * .8:
                break
        print(f"\nDataset: {name}")
        print(  f"  N={len(inputs)}, {ohw:.0f}% one-hit-wonders, top {100*width/N:.0f}% keys used in {100*acc/N:.0f}% of requests\n  max freq: {max(ctr.values())}, mean freq: {sum(ctr.values())/len(ctr):.2f}")

    def compare(inputs):
        cache_sizes = (10, 25, 50, 100, 200, 400, 800)
        hit_rates = []
        for cache_size in cache_sizes:
            rates = []
            for C in kinds:
                cache = C(f, cache_size)
                assert [cache.get(x) for x in inputs] == [f(x) for x in inputs]
                rates.append(cache.hits/(cache.hits + cache.misses))
            hit_rates.append(rates)

        print("\nCache hit rates at various cache sizes")
        print(f"{'cache_size ---------->':20}\t", '\t'.join(f"  {sz}" for sz in cache_sizes), sep='')
        hr = (col[0] for col in hit_rates)
        formatted_rates = (f"{100*rate:4.0f}%" for rate in hr)
        print(f"{kinds[0].__name__ + ' (baseline)':20}\t", '\t'.join(formatted_rates), sep='')
        for idx, kind in enumerate(kinds[1:]):
            hr = (col[idx+1] - col[0] for col in hit_rates)
            formatted_rates = (f"{100*rate:>+4.0f}%" for rate in hr)
            print(f"{kind.__name__:20}\t", '\t'.join(formatted_rates), sep='')

    N = 1600

    from scipy.stats import zipf
    def z(a):
        inputs = zipf.rvs(a, size=N).astype('float64')
        print_input_stats(f"zipf alpha={a}", inputs)
        compare(inputs)
    for a in (1.2, 1.1, 1.05):
        z(a)

    # yule-simon is a very similar distribution to zipf, so just show zipf
    # from scipy.stats import yulesimon
    # def ys(a):
    #     inputs = yulesimon.rvs(a, size=N).astype('float64')
    #     print_input_stats(f"yule-simon {a}", inputs)
    #     compare(inputs)
    # for a in (.1, .05, .025):
    #     ys(a)

if __name__ == '__main__':
    tests()
