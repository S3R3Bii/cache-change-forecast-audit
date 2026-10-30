"""Equal-object LRU with resident state preserved across one authored resize."""

from collections import OrderedDict


def simulate(ids, capacity=512, change_at=None, change_to=None, block_size=1000):
    if type(block_size) is not int or block_size <= 0:
        raise ValueError("positive request block size required")
    if type(capacity) is not int or capacity <= 0:
        raise ValueError("positive integer capacity required")
    if change_at is not None and (
        type(change_at) is not int
        or not 0 <= change_at <= len(ids)
        or type(change_to) is not int
        or change_to <= 0
    ):
        raise ValueError("invalid resize")
    if len(ids) % block_size:
        raise ValueError("incomplete request block")
    cache = OrderedDict()
    misses = []
    current = capacity
    for i, key in enumerate(ids):
        if type(key) is not int or key < 0:
            raise ValueError("nonnegative ordinal identity")
        if change_at is not None and i == change_at:
            current = change_to
            while len(cache) > current:
                cache.popitem(last=False)
        miss = int(key not in cache)
        misses.append(miss)
        if not miss:
            cache.move_to_end(key)
        else:
            cache[key] = None
            if len(cache) > current:
                cache.popitem(last=False)
    return misses, [
        sum(misses[i : i + block_size]) for i in range(0, len(misses), block_size)
    ]
