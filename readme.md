# S3FIFO.py

My implementation of the [S3-FIFO cache eviction algorithm](https://blog.jasony.me/system/cache/2023/08/01/s3fifo).

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

## Example use:

```python
cache = S3Fifo(some_callable, maximum_number_of_cached_values)

# Gets the return value of `some_callable(some_key)` or the saved
# return value of an earlier call of `some_callable(some_key)`.
value = cache.get(some_key)
```

`get` and `some_callable` must accept a single value and that value must be
usable as a `dict` key. If you want to key on multiple values then use a
tuple or a hash of those of values as appropriate.

## Performance testing

I don't want to get the real world data, but supposedly the distribution of
request keys is similar to a Zipf distribution, so I've tested with that.

I compared S3FIFO with a simple FIFO cache and python's functools.lru_cache,
neither of which are state of the art, but they are very easily available!

In my tests, S3FIFO has a strong relative advantage over those simple
competitors when the cache is very small and a modest advantage or no
disadvantage when the cache is large. I am a hack and a fraud, so I didn't
do significance testing.

Run my benchmarks with `python3 tests.py`. You'll need scipy.

```
$ python3 tests.py

Dataset: zipf alpha=1.2
  N=1600, 32% one-hit-wonders, top 19% keys used in 80% of requests
  max freq: 267, mean freq: 2.58

Cache hit rates at various cache sizes
cache_size ---------->	  10	  25	  50	  100	  200	  400	  800
S3FIFO (baseline)   	  38%	  47%	  52%	  56%	  58%	  61%	  61%
S3FIFO3             	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp
S3FIFO4             	  -0pp	  -0pp	  -1pp	  -2pp	  -1pp	  -2pp	  +0pp
LRU                 	 -13pp	 -10pp	  -8pp	  -4pp	  -1pp	  -0pp	  +0pp
FIFO                	 -16pp	 -15pp	 -13pp	  -9pp	  -5pp	  -3pp	  +0pp
EagerEvictionS3FIFO 	  +0pp	  -1pp	  -2pp	  -3pp	  -4pp	  -5pp	  -4pp

Dataset: zipf alpha=1.1
  N=1600, 55% one-hit-wonders, top 42% keys used in 80% of requests
  max freq: 158, mean freq: 1.62

Cache hit rates at various cache sizes
cache_size ---------->	  10	  25	  50	  100	  200	  400	  800
S3FIFO (baseline)   	  20%	  26%	  29%	  32%	  34%	  37%	  38%
S3FIFO3             	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp
S3FIFO4             	  -1pp	  -1pp	  -0pp	  -1pp	  -1pp	  -0pp	  -1pp
LRU                 	 -11pp	 -10pp	  -8pp	  -5pp	  -2pp	  -1pp	  -0pp
FIFO                	 -12pp	 -12pp	 -11pp	  -8pp	  -6pp	  -4pp	  -1pp
EagerEvictionS3FIFO 	  -1pp	  -1pp	  -2pp	  -3pp	  -4pp	  -4pp	  -4pp

Dataset: zipf alpha=1.05
  N=1600, 72% one-hit-wonders, top 57% keys used in 80% of requests
  max freq: 80, mean freq: 1.30

Cache hit rates at various cache sizes
cache_size ---------->	  10	  25	  50	  100	  200	  400	  800
S3FIFO (baseline)   	  12%	  15%	  16%	  18%	  20%	  22%	  23%
S3FIFO3             	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp	  +0pp
S3FIFO4             	  +0pp	  -1pp	  +0pp	  -0pp	  -1pp	  -1pp	  -1pp
LRU                 	  -8pp	  -8pp	  -6pp	  -4pp	  -3pp	  -1pp	  -0pp
FIFO                	  -8pp	  -9pp	  -8pp	  -6pp	  -5pp	  -3pp	  -2pp
EagerEvictionS3FIFO 	  -1pp	  -2pp	  -2pp	  -2pp	  -3pp	  -3pp	  -3pp
```

## References

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
`ensure_free()`.
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

## Origin

I got nerd-sniped [here](https://lobste.rs/s/xszyoz/fifo_queues_are_all_you_need_for_cache#c_r29nxa), where you can read more about my difficulties in understanding the pseudocode and the author's implementations and find links to the author's implementations.
