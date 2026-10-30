# Recheck a miss-rate forecast after changing cache capacity

A forecast built under one cache capacity may mislead a storage planner after a configuration change. This independent study tests that problem using licensed recorded request prefixes and explicitly simulated equal-object LRU caches.

**Current state: source and development checked; protected final evaluation pending.** The previous-block baseline has development MAE 0.0731; the best of three fixed linear settings has MAE 0.081148. The baseline wins this comparison. No final-volume cache simulation or score has been extracted.

The [protocol](PROTOCOL.md) fixes six files selected by size metadata, 200,000-request prefixes, volume/time separation, every model setting and the simulated capacity changes. Independent source reconstruction checks all 1.2 million public ordinal IDs. The future-access field is excluded. The [offline exercise](IMPLEMENTATION_EXERCISE.md) keeps configuration context explicit.

Results concern miss fractions per 1,000 recorded requests under authored equal-object LRU. Slots are not RAM bytes; production latency, IOPS, energy, adoption and savings are unmeasured. Source-derived sequences are attributed under CC BY 4.0; complete raw trace objects and formal-publication projects remain private.
