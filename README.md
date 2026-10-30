# Recheck a miss-rate forecast after changing cache capacity

A forecast built under one cache capacity may mislead a storage planner after a configuration change. This independent study will test that problem using licensed public request traces and explicitly simulated equal-object LRU caches.

**State: protocol only.** No trace values, simulated miss counts or model results have been acquired. The [protocol](PROTOCOL.md) fixes a six-file metadata-selected cohort, bounded request prefixes, separate volumes/time windows, every model setting and the simulated capacity changes. Results will concern request-block miss fractions, not production latency, IOPS, energy or savings.
