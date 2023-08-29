# S3FIFO.py

My implementation of something like the [S3-FIFO cache eviction algorithm](https://blog.jasony.me/system/cache/2023/08/01/s3fifo).
My algorithm differs in some ways from the author's implementations and should not be used as a reference.

I got nerd-sniped [here](https://lobste.rs/s/xszyoz/fifo_queues_are_all_you_need_for_cache#c_r29nxa), where you can read more about my difficulties in understanding the pseudocode and the author's implementations and find links to the author's implementations.

## Performance

The author of S3FIFO has published research claiming it performs well on many real-world datasets and is adapted
for the common case that a large proportion of requests are unique within
some reasonable time frame.

I don't want to get the real world data, but supposedly the distribution of
request keys is similar to a Zipf distribution, so I've tested with that.
I compared S3FIFO with a simple FIFO and python's `functools.lru_cache`,
neither of which are state of the art.

In my tests, S3FIFO has a strong relative advantage when the cache is very
small and a slight relative disadvantage when the cache is large.

Here's some numbers I generated on my machine for various zipf distributions.
I don't know which if any of these distributions are representative of real-world data.
"One-hit-wonders" are requests whose key occurs only once in the dataset.

```
$ python3 s3fifo.py

Dataset: zipf alpha=1.2
  N=1600, 33% one-hit-wonders, top 20% keys used in 80% of requests
  max freq: 256, mean freq: 2.52

Cache hit rates at various cache sizes
cache_size ---------->	  10	  25	  50	  100	  200	  400	  800
S3FIFO (baseline)   	  39%	  47%	  51%	  53%	  54%	  55%	  56%
LRU                 	 -14%	 -10%	  -7%	  -3%	  +2%	  +4%	  +4%
FIFO                	 -18%	 -15%	 -12%	  -8%	  -2%	  +2%	  +4%

Dataset: zipf alpha=1.1
  N=1600, 59% one-hit-wonders, top 45% keys used in 80% of requests
  max freq: 164, mean freq: 1.55

Cache hit rates at various cache sizes
cache_size ---------->	  10	  25	  50	  100	  200	  400	  800
S3FIFO (baseline)   	  22%	  26%	  27%	  29%	  30%	  31%	  32%
LRU                 	 -12%	  -8%	  -4%	  -2%	  +1%	  +3%	  +4%
FIFO                	 -13%	 -12%	  -8%	  -5%	  -2%	  +0%	  +2%

Dataset: zipf alpha=1.05
  N=1600, 75% one-hit-wonders, top 59% keys used in 80% of requests
  max freq: 70, mean freq: 1.26

Cache hit rates at various cache sizes
cache_size ---------->	  10	  25	  50	  100	  200	  400	  800
S3FIFO (baseline)   	  10%	  12%	  14%	  15%	  16%	  17%	  18%
LRU                 	  -7%	  -6%	  -4%	  -2%	  +0%	  +2%	  +2%
FIFO                	  -7%	  -7%	  -6%	  -4%	  -2%	  -0%	  +1%
```
