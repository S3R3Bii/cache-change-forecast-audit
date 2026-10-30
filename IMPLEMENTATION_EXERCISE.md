# Keep configuration context with a forecast

This offline exercise accepts three completed miss counts, **newest first**, each out of 1,000 requests. It uses the frozen linear model and previous-block baseline. Inputs are authored examples, not real incidents.

~~~sh
python src/review_cli.py examples/authored-stable-context.json
python src/review_cli.py examples/authored-changed-context.json
python src/review_cli.py examples/unknown-history.json
~~~

A declared capacity change adds a reminder to collect post-change history and recheck the configuration-blind forecast. That message is teaching context, not a validated alert policy or recommendation to change a real cache. Missing history stays UNKNOWN.

Implementation tasks:
1. Follow the exact three lag blocks; exclude the target block and future-access field.
2. Check the same request sequence under a 512-to-128 slot shrink and a 512-to-2,048 expansion.
3. Preserve resident state: shrinking evicts least-recent entries, while expansion cannot resurrect old evictions.
4. Compare both forecast errors and retain a previous-block win. A fitted model is not automatically better.
5. Explain why equal-object slots and 1,000-request blocks do not measure RAM bytes, IOPS, latency or energy.

The CLI makes no source request, sends no message and changes no cache. Real deployment needs byte-aware behavior, operation types, timing, concurrency and production measurements.
