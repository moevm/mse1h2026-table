import datetime
import json
import os
import subprocess
import sys
import time

import requests

from scripts.deploy import (
    get_compose_dir,
    get_compose_file,
    get_nextcloud_url,
)
from scripts.utils import success, error, now


_MEM_UNITS = {
    "TiB": 1024 * 1024.0,
    "GiB": 1024.0,
    "MiB": 1.0,
    "KiB": 1 / 1024,
    "TB": 1000 * 1000.0,
    "GB": 1000.0,
    "MB": 1.0,
    "kB": 1 / 1024,
    "B": 1 / (1024 * 1024),
}


def _parse_mem_mb(s):
    s = s.strip()
    for unit in sorted(_MEM_UNITS, key=lambda u: -len(u)):
        if s.endswith(unit):
            try:
                return float(s[:-len(unit)]) * _MEM_UNITS[unit]
            except ValueError:
                return 0.0
    return 0.0


def _docker_stats(compose_dir, compose_file):
    ids_proc = subprocess.run(
        [
            "docker", "compose", "-f", str(compose_file),
            "ps", "-q",
        ],
        cwd=compose_dir, text=True, capture_output=True,
    )
    if ids_proc.returncode != 0:
        return {}, {"cpu_percent": 0.0, "mem_usage_mb": 0.0}

    ids = [
        line.strip() for line in ids_proc.stdout.splitlines() if line.strip()
    ]
    if not ids:
        return {}, {"cpu_percent": 0.0, "mem_usage_mb": 0.0}

    stats_proc = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", *ids],
        text=True, capture_output=True,
    )
    if stats_proc.returncode != 0:
        return {}, {"cpu_percent": 0.0, "mem_usage_mb": 0.0}

    containers = {}
    total_cpu = 0.0
    total_mem = 0.0
    for line in stats_proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        name = item.get("Name") or item.get("Container") or "?"
        cpu_str = item.get("CPUPerc", "0%").rstrip("%")
        mem_perc_str = item.get("MemPerc", "0%").rstrip("%")
        mem_usage_str = item.get("MemUsage", "0MiB / 0MiB").split(" / ")[0]

        try:
            cpu = float(cpu_str)
        except ValueError:
            cpu = 0.0
        try:
            mem_perc = float(mem_perc_str)
        except ValueError:
            mem_perc = 0.0
        mem_mb = _parse_mem_mb(mem_usage_str)

        containers[name] = {
            "cpu_percent": round(cpu, 2),
            "mem_usage_mb": round(mem_mb, 1),
            "mem_percent": round(mem_perc, 2),
        }
        total_cpu += cpu
        total_mem += mem_mb

    return containers, {
        "cpu_percent": round(total_cpu, 2),
        "mem_usage_mb": round(total_mem, 1),
    }


def _api_latency(base_url, samples, path="/status.php", timeout=30.0):
    if not path.startswith("/"):
        path = "/" + path
    url = f"{base_url.rstrip('/')}{path}"
    timings = []
    errors = 0
    for _ in range(samples):
        start = time.time()
        try:
            resp = requests.get(url, timeout=timeout)
            elapsed_ms = (time.time() - start) * 1000
            if resp.status_code == 200:
                timings.append(elapsed_ms)
            else:
                errors += 1
        except requests.RequestException:
            errors += 1

    result = {
        "endpoint": path,
        "samples": samples,
        "errors": errors,
    }
    if timings:
        result["avg_ms"] = int(sum(timings) / len(timings))
        result["min_ms"] = int(min(timings))
        result["max_ms"] = int(max(timings))
    else:
        result["avg_ms"] = None
        result["min_ms"] = None
        result["max_ms"] = None
    return result


def _active_sessions(compose_dir, compose_file):
    sql = (
        "SELECT count(*) FROM oc_authtoken "
        "WHERE last_activity > extract(epoch from now())::bigint - 300"
    )
    cmd = [
        "docker", "compose", "-f", str(compose_file),
        "exec", "-T", "db", "sh", "-c",
        f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -t -A -c "{sql}"',
    ]
    proc = subprocess.run(cmd, cwd=compose_dir, text=True, capture_output=True)
    if proc.returncode != 0:
        return {"active_5min": None}

    out = proc.stdout.strip().splitlines()
    if not out:
        return {"active_5min": None}
    try:
        return {"active_5min": int(out[-1].strip())}
    except ValueError:
        return {"active_5min": None}


def _disk_free_gb(compose_dir, compose_file):
    cmd = [
        "docker", "compose", "-f", str(compose_file),
        "exec", "-T", "app", "sh", "-c",
        "df -B 1G --output=avail /var/www/html | tail -n 1",
    ]
    proc = subprocess.run(cmd, cwd=compose_dir, text=True, capture_output=True)
    if proc.returncode != 0:
        return None
    try:
        return int(proc.stdout.strip())
    except ValueError:
        return None


def _collect(args, compose_dir, compose_file):
    base_url = get_nextcloud_url(args)
    samples = max(1, getattr(args, "samples", 5))
    path = getattr(args, "path", None) or "/status.php"
    timeout = getattr(args, "response_timeout", 30.0)

    containers, totals = _docker_stats(compose_dir, compose_file)
    api = _api_latency(base_url, samples, path=path, timeout=timeout)
    sessions = _active_sessions(compose_dir, compose_file)
    disk_free = _disk_free_gb(compose_dir, compose_file)

    return {
        "containers": containers,
        "containers_total": totals,
        "api": api,
        "sessions": sessions,
        "disk_free_gb": disk_free,
        "timestamp": now(),
    }


def _write_payload(payload, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(output_dir, f"metrics_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def _print_payload(payload, fmt):
    if fmt == "json":
        print(json.dumps(payload, ensure_ascii=False), flush=True)
    else:
        for k, v in payload.items():
            print(f"{k}: {v}")
        print("---", flush=True)


def monitor_resources(args):
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    interval = max(getattr(args, "interval", 0.0), 0.0)
    count = getattr(args, "count", 1)
    output_dir = getattr(args, "output_dir", None)
    quiet = getattr(args, "quiet", False)

    if interval <= 0 or count == 1:
        payload = _collect(args, compose_dir, compose_file)
        if output_dir:
            _write_payload(payload, output_dir)
        if not quiet:
            success(payload, args.output)
        sys.exit(0)

    emitted = 0
    try:
        while True:
            payload = _collect(args, compose_dir, compose_file)
            if output_dir:
                _write_payload(payload, output_dir)
            if not quiet:
                _print_payload(payload, args.output)
            emitted += 1
            if 0 < count <= emitted:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    sys.exit(0)