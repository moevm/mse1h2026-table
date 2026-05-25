#!/usr/bin/env python3
"""
Склейка stepped-прогона loadtest с параллельными снимками `monitor resources`:
выводит CPU/RAM по стадиям и пиковые значения.

Запуск: --monitor-dir <папка JSON-снимков> --results-dir <папка прогона>
"""
import argparse
import json
from datetime import datetime
from pathlib import Path


STAGES = [
    ("baseline", -1e9, 0, 0),
    ("stage1 (50 users)", 0, 60, 50),
    ("stage2 (100 users)", 60, 180, 100),
    ("stage3 (200 users)", 180, 360, 200),
    ("stage4 (300 users)", 360, 600, 300),
    ("cooldown", 600, 1e9, 0),
]


def parse_results_start(results_dir):
    folder = results_dir.name
    y, m, d = folder[:10].split("-")
    hh, mm, ss = folder[11:].split("-")
    return datetime(
        int(y), int(m), int(d), int(hh), int(mm), int(ss),
    ).timestamp()


def load_snapshots(monitor_dir):
    snapshots = []
    for f in sorted(monitor_dir.glob("*.json")):
        with f.open() as fh:
            data = json.load(fh)
        snapshots.append({
            "ts": datetime.fromisoformat(data["timestamp"]).timestamp(),
            "containers": data["containers"],
            "api_avg_ms": data["api"]["avg_ms"],
            "total_cpu": data["containers_total"]["cpu_percent"],
            "total_mem": data["containers_total"]["mem_usage_mb"],
        })
    return snapshots


def summarize_stage(samples):
    def avg(getter):
        vals = [getter(s) for s in samples]
        return sum(vals) / len(vals)

    return {
        "samples": len(samples),
        "app_cpu_avg": avg(
            lambda s: s["containers"]["app-server"]["cpu_percent"]
        ),
        "app_cpu_peak": max(
            s["containers"]["app-server"]["cpu_percent"] for s in samples
        ),
        "app_mem_avg": avg(
            lambda s: s["containers"]["app-server"]["mem_usage_mb"]
        ),
        "app_mem_peak": max(
            s["containers"]["app-server"]["mem_usage_mb"] for s in samples
        ),
        "cron_cpu_avg": avg(
            lambda s: s["containers"]["nextcloud-cron-worker"]["cpu_percent"]
        ),
        "oo_cpu_avg": avg(
            lambda s:
            s["containers"]["onlyoffice-document-server"]["cpu_percent"]
        ),
        "total_cpu_avg": avg(lambda s: s["total_cpu"]),
        "total_mem_avg": avg(lambda s: s["total_mem"]),
        "api_ms_avg": avg(lambda s: s["api_avg_ms"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--monitor-dir", required=True, type=Path,
        help="Directory with monitor JSON snapshots",
    )
    parser.add_argument(
        "--results-dir", required=True, type=Path,
        help="Loadtest results dir (used for run start timestamp from name)",
    )
    args = parser.parse_args()

    lt_start = parse_results_start(args.results_dir)
    print(f"Loadtest start: {datetime.fromtimestamp(lt_start)}")

    snapshots = load_snapshots(args.monitor_dir)
    print(f"Snapshots: {len(snapshots)}")
    if not snapshots:
        return
    print(f"First snapshot: {datetime.fromtimestamp(snapshots[0]['ts'])}")
    print(f"Last snapshot:  {datetime.fromtimestamp(snapshots[-1]['ts'])}")

    print(
        f"\n{'Stage':<22} {'n':>3} "
        f"{'app CPU%':>9} {'app RAM MB':>11} "
        f"{'cron CPU%':>10} {'OO CPU%':>9} "
        f"{'total CPU%':>10} {'total MB':>9} "
        f"{'API ms':>7}"
    )
    print("-" * 100)

    stage_summary = {}
    for name, t0, t1, users in STAGES:
        samples = [
            s for s in snapshots
            if t0 <= (s["ts"] - lt_start) < t1
        ]
        if not samples:
            continue
        st = summarize_stage(samples)
        st["users"] = users
        stage_summary[name] = st

        print(
            f"{name:<22} {st['samples']:>3} "
            f"{st['app_cpu_avg']:>9.1f} {st['app_mem_avg']:>11.1f} "
            f"{st['cron_cpu_avg']:>10.1f} {st['oo_cpu_avg']:>9.1f} "
            f"{st['total_cpu_avg']:>10.1f} {st['total_mem_avg']:>9.1f} "
            f"{st['api_ms_avg']:>7.1f}"
        )

    baseline = stage_summary.get("baseline")
    peak_stage = stage_summary.get("stage4 (300 users)")

    if baseline and peak_stage:
        print("\n=== Derived model (averages over the stage) ===")
        d_mem = peak_stage["app_mem_avg"] - baseline["app_mem_avg"]
        d_cpu = peak_stage["app_cpu_avg"] - baseline["app_cpu_avg"]
        users = peak_stage["users"]
        print(f"Baseline app-server RAM: {baseline['app_mem_avg']:.1f} MB")
        print(
            f"Stage4 (300 users) app-server RAM: "
            f"{peak_stage['app_mem_avg']:.1f} MB"
        )
        print(f"Delta RAM (avg): {d_mem:.1f} MB for {users} users")
        if users > 0:
            print(f"  -> {d_mem / users:.2f} MB per simulated user (avg)")
        print(f"Baseline app-server CPU: {baseline['app_cpu_avg']:.1f}%")
        print(
            f"Stage4 (300 users) app-server CPU: "
            f"{peak_stage['app_cpu_avg']:.1f}%"
        )
        print(f"Delta CPU (avg): {d_cpu:.1f}%")
        if d_cpu > 0:
            print(f"  -> {users / (d_cpu / 100):.1f} users per core (avg)")

    lt_samples = [
        s for s in snapshots
        if 0 <= (s["ts"] - lt_start) < 600
    ]
    if lt_samples:
        print("\n=== Peak (max) over the whole loadtest window ===")
        peak_app_cpu = max(
            s["containers"]["app-server"]["cpu_percent"] for s in lt_samples
        )
        peak_app_mem = max(
            s["containers"]["app-server"]["mem_usage_mb"] for s in lt_samples
        )
        peak_total_cpu = max(s["total_cpu"] for s in lt_samples)
        peak_total_mem = max(s["total_mem"] for s in lt_samples)
        peak_api = max(s["api_avg_ms"] for s in lt_samples)
        print(f"app-server peak CPU: {peak_app_cpu:.1f}%")
        print(f"app-server peak RAM: {peak_app_mem:.1f} MB")
        print(f"All containers peak CPU: {peak_total_cpu:.1f}%")
        print(f"All containers peak RAM: {peak_total_mem:.1f} MB")
        print(f"API latency peak: {peak_api:.1f} ms")


if __name__ == "__main__":
    main()
