def tests():
    from s3fifo import S3FIFO
    from other_fifos import EagerEvictionS3FIFO, S3FIFO3, S3FIFO4, FIFO, LRU
    # Simple test

    f = lambda x: 2*x
    cache = S3FIFO(f, 20)
    assert [cache.get(x) for x in range(30)] == [f(x) for x in range(30)]

    # Performance comparisons

    from collections import Counter

    kinds = (S3FIFO, S3FIFO3, S3FIFO4, LRU, FIFO, EagerEvictionS3FIFO)

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
            formatted_rates = (f"{100*rate:>+4.0f}pp" for rate in hr)
            print(f"{kind.__name__:20}\t", '\t'.join(formatted_rates), sep='')

    N = 1600

    from scipy.stats import zipf
    def z(a):
        inputs = zipf.rvs(a, size=N).astype('float64')
        print_input_stats(f"zipf alpha={a}", inputs)
        compare(inputs)
    for _ in range(1):
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
