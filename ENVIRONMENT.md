# Environment and units

Source capture/projection: CPython 3.10.11, Requests 2.32.3 and private task-local zstandard 0.25.0. Source decoding is optional for public saved-data replay. The independent byte parser checks exact compressed objects and every public ordinal before analytical derivation.

The main simulator uses standard-library OrderedDict. Main model fitting and reported metrics use exact Fraction arithmetic; the independent simulator uses a resident dictionary and last-access min-heap, and independent regression uses NumPy 2.2.5. Figures use Matplotlib 3.10.9; PDF extraction uses pypdf 6.10.0 under CPython 3.12.14, with Tectonic compilation and Poppler rendering.

Forecast units are miss fractions per 1,000-request block under simulated equal-object LRU. Slots are not bytes; source object sizes/read-write operations, actual latency, IOPS, energy, throughput and production outcomes are unmeasured by this exercise. All scenarios use a cold prefix start and preserve resident state at the authored capacity change.

Public replay requires full Git history and a fresh external output, uses saved ordinal prefixes, and makes no source requests. Original execution runtimes stay separate from new replay runtimes. Two-runtime isolated replay and exact CI/tag evidence are release gates, not protocol-stage achievements.
