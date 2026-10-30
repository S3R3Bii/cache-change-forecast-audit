"""Fetch only six protocol-pinned public objects; preserve every attempt."""

import argparse, hashlib, json, time
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import requests


class PublicAuth(requests.auth.AuthBase):
    def __call__(self, r):
        return r


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(p, v):
    p.write_bytes((json.dumps(v, indent=2) + "\n").encode())


def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1048576), b""):
            h.update(b)
    return h.hexdigest()


def acquire(root, private, retry=False):
    plan = json.loads((root / "data/source_plan.json").read_text())
    private.mkdir(parents=True, exist_ok=True)
    path = private / "receipts.json"
    records = json.loads(path.read_text()) if path.exists() else []
    if retry:
        denied = [r for r in records if r["status"] == 429]
        assert len(denied) == 1 and not any(r["retry_attempt"] for r in records)
        assert datetime.now(timezone.utc) >= datetime.fromisoformat(
            denied[0]["retry_not_before_utc"]
        )
    else:
        assert all(
            r["status"] == 200 for r in records
        ), "Prior source failure retained; no automatic repetition"
    done = {r["trace"] for r in records if r["status"] == 200}
    for r in records:
        if r["status"] == 200:
            assert digest(private / r["private_body"]) == r["sha256"]
    with requests.Session() as session:
        session.auth = PublicAuth()
        session.headers["User-Agent"] = (
            "cache-change-forecast-audit/0.1 (+https://github.com/S3R3Bii/cache-change-forecast-audit)"
        )
        for item in plan["traces"]:
            if item["trace"] in done:
                continue
            assert len(records) < plan["maximum_get_attempts"]
            previous = (
                datetime.fromisoformat(records[-1]["start_utc"]).timestamp()
                if records
                else 0
            )
            time.sleep(
                max(0, plan["minimum_get_spacing_seconds"] - (time.time() - previous))
            )
            session.cookies.clear()
            start = utc()
            target = private / f'{len(records)+1:02d}-{item["trace"]}.partial'
            size = 0
            status = None
            headers = {}
            try:
                with session.get(
                    item["url"], timeout=(15, 60), stream=True, allow_redirects=False
                ) as response:
                    status = response.status_code
                    headers = {
                        k.lower(): v
                        for k, v in response.headers.items()
                        if k.lower()
                        in [
                            "content-length",
                            "content-type",
                            "content-encoding",
                            "etag",
                            "last-modified",
                            "retry-after",
                            "date",
                        ]
                    }
                    assert (
                        headers.get("content-encoding", "identity") == "identity"
                    ), "Unexpected transport encoding"
                    cap = plan["maximum_object_bytes"] if status == 200 else 1048576
                    with target.open("xb") as stream:
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            assert (
                                size <= cap
                                and sum(r["bytes"] for r in records) + size
                                <= plan["maximum_total_bytes"]
                            ), "capture bound"
                            stream.write(chunk)
                record = dict(
                    trace=item["trace"],
                    url=item["url"],
                    start_utc=start,
                    end_utc=utc(),
                    status=status,
                    headers=headers,
                    bytes=size,
                    sha256=digest(target),
                    private_body=target.name,
                    retry_attempt=retry,
                )
                if status == 429:
                    after = headers.get("retry-after")
                    try:
                        seconds = max(60, int(after))
                    except (TypeError, ValueError):
                        try:
                            seconds = max(
                                60,
                                parsedate_to_datetime(after).timestamp() - time.time(),
                            )
                        except (TypeError, ValueError, AttributeError):
                            seconds = 60
                    record["retry_not_before_utc"] = datetime.fromtimestamp(
                        time.time() + seconds, timezone.utc
                    ).isoformat()
                records.append(record)
                save(path, records)
                assert status == 200, "Source unavailable; exact attempt retained"
                assert (
                    size == item["expected_bytes"] == int(headers["content-length"])
                    and headers["etag"] == item["expected_etag"]
                ), "Pinned metadata changed"
                final = target.with_suffix(".zst")
                target.rename(final)
                record["private_body"] = final.name
                save(path, records)
                print(
                    json.dumps(
                        {
                            k: record[k]
                            for k in [
                                "trace",
                                "status",
                                "bytes",
                                "start_utc",
                                "end_utc",
                            ]
                        }
                    ),
                    flush=True,
                )
            except Exception as error:
                save(
                    private / f"failure-{len(records):02d}.json",
                    dict(
                        trace=item["trace"],
                        start_utc=start,
                        end_utc=utc(),
                        status=status,
                        received_bytes=size,
                        partial_file=target.name,
                        error_type=type(error).__name__,
                        message=str(error),
                    ),
                )
                raise
    print(
        json.dumps(
            dict(
                status="COMPLETE_COMPRESSED_OBJECTS_CAPTURED",
                objects=len(done | {r["trace"] for r in records if r["status"] == 200}),
                bytes=sum(r["bytes"] for r in records),
            )
        )
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--private", required=True, type=Path)
    p.add_argument("--retry-rate-limited", action="store_true")
    a = p.parse_args()
    acquire(Path(__file__).resolve().parents[1], a.private, a.retry_rate_limited)
