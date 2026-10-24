"""Turn captures already in MinIO into labelled flow records.

Runs inside a worker container, which has the converter and the serving code:

    docker cp training/collect_testbed_flows.py worker2:/tmp/
    docker exec worker2 python3 /tmp/collect_testbed_flows.py \
        --label 1 --last 6 --out /tmp/attack.csv

Label 1 for windows captured while an attack was running, 0 for idle ones.
Concatenate both into training/data/testbed_<layer>.csv.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

import pandas as pd

from ddos_worker.config import WorkerConfig
from ddos_worker.flowmeter import pcap_to_csv, read_flows


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--label", type=int, required=True, choices=(0, 1))
    p.add_argument("--out", required=True)
    p.add_argument("--bucket", default=None, help="defaults to this worker's bucket")
    p.add_argument("--last", type=int, default=6, help="newest N captures")
    p.add_argument("--since", default=None, help="ISO timestamp, overrides --last")
    p.add_argument("--until", default=None, help="ISO timestamp")
    p.add_argument("--work-dir", default="/tmp/collect")
    return p.parse_args(argv)


def _stamp(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def select(objects, args):
    since, until = _stamp(args.since), _stamp(args.until)
    if since or until:
        chosen = [
            o for o in objects
            if (not since or o.last_modified >= since)
            and (not until or o.last_modified <= until)
        ]
    else:
        chosen = sorted(objects, key=lambda o: o.last_modified)[-args.last:]
    return sorted(chosen, key=lambda o: o.last_modified)


def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = WorkerConfig.from_env(os.environ)
    bucket = args.bucket or cfg.minio_bucket

    from minio import Minio

    store = Minio(
        cfg.minio_endpoint,
        access_key=cfg.minio_access_key,
        secret_key=cfg.minio_secret_key,
        secure=False,
    )

    chosen = select(list(store.list_objects(bucket, recursive=True)), args)
    if not chosen:
        print(f"no captures selected in {bucket}", file=sys.stderr)
        return 1

    work = Path(args.work_dir)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    frames = []
    for obj in chosen:
        pcap = work / Path(obj.object_name).name
        store.fget_object(bucket, obj.object_name, str(pcap))
        try:
            csv = pcap_to_csv(pcap, work / "csv", cfm_home=cfg.cfm_home,
                              timeout=cfg.flowmeter_timeout, java_opts=cfg.java_opts)
        except Exception as exc:
            print(f"  {obj.object_name}: {exc}", file=sys.stderr)
            continue
        frame = read_flows(csv)
        frame["capture"] = obj.object_name
        frame["captured_at"] = obj.last_modified.isoformat()
        frames.append(frame)
        print(f"  {obj.object_name}: {len(frame)} flows")

    if not frames:
        print("no flows extracted", file=sys.stderr)
        return 1

    out = pd.concat(frames, ignore_index=True)
    out["y"] = args.label
    out["layer"] = cfg.layer
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(args.out, index=False)
    print(f"{len(out)} flows from {len(frames)} captures -> {args.out} (label={args.label})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
