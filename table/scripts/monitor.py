import os
import platform
import shutil
import subprocess
import time
import json
import datetime
import requests
from typing import Optional, Tuple
from scripts.utils import now, print_output


def _run_command(cmd):
    try:
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return None


def _read_proc_stat() -> Optional[Tuple[int, int]]:
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            line = f.readline()
    except OSError:
        return None

    parts = line.strip().split()
    if not parts or parts[0] != "cpu":
        return None

    values = [int(p) for p in parts[1:] if p.isdigit()]
    if len(values) < 4:
        return None

    idle = values[3]
    if len(values) > 4:
        idle += values[4]

    total = sum(values)
    return total, idle


def _cpu_percent_linux(sample_interval: float) -> Optional[float]:
    snap1 = _read_proc_stat()
    if not snap1:
        return None

    time.sleep(max(sample_interval, 0.05))
    snap2 = _read_proc_stat()
    if not snap2:
        return None

    total_delta = snap2[0] - snap1[0]
    idle_delta = snap2[1] - snap1[1]
    if total_delta <= 0:
        return None

    return 100.0 * (1.0 - (idle_delta / total_delta))


def _cpu_percent_windows() -> Optional[float]:
    proc = _run_command(["wmic", "cpu", "get", "loadpercentage", "/value"])
    if proc and proc.returncode == 0:
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("loadpercentage="):
                try:
                    return float(line.split("=", 1)[1])
                except ValueError:
                    return None

    proc = _run_command(
        [
            "typeperf",
            "\\Processor(_Total)\\% Processor Time",
            "-sc",
            "1",
        ]
    )
    if not proc or proc.returncode != 0:
        return None

    for line in proc.stdout.splitlines():
        if "% Processor Time" in line:
            continue
        if "," in line:
            try:
                value = line.split(",", 1)[1].strip().strip("\"")
                return float(value)
            except ValueError:
                return None

    return None


def _cpu_percent_fallback() -> Optional[float]:
    try:
        load = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        return min(100.0, max(0.0, (load / cpu_count) * 100.0))
    except (AttributeError, OSError):
        return None


def get_cpu_percent(sample_interval: float = 0.2) -> Optional[float]:
    system = platform.system().lower()
    if system == "linux":
        value = _cpu_percent_linux(sample_interval)
        if value is not None:
            return value
    elif system == "windows":
        value = _cpu_percent_windows()
        if value is not None:
            return value

    return _cpu_percent_fallback()


def get_memory_mb() -> Tuple[Optional[float], Optional[float]]:
    system = platform.system().lower()

    if system == "linux":
        total = None
        available = None
        try:
            with open("/proc/meminfo", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        total = float(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        available = float(line.split()[1])
        except OSError:
            return None, None

        if total is None or available is None:
            return None, None

        used_kb = total - available
        return used_kb / 1024.0, total / 1024.0

    if system == "windows":
        proc = _run_command(
            [
                "wmic",
                "OS",
                "get",
                "FreePhysicalMemory,TotalVisibleMemorySize",
                "/value",
            ]
        )
        if not proc or proc.returncode != 0:
            return None, None

        free_kb = None
        total_kb = None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("freephysicalmemory="):
                try:
                    free_kb = float(line.split("=", 1)[1])
                except ValueError:
                    free_kb = None
            elif line.lower().startswith("totalvisiblememorysize="):
                try:
                    total_kb = float(line.split("=", 1)[1])
                except ValueError:
                    total_kb = None

        if free_kb is None or total_kb is None:
            return None, None

        used_kb = total_kb - free_kb
        return used_kb / 1024.0, total_kb / 1024.0

    return None, None


def get_disk_free_gb(path: str) -> Optional[float]:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None

    return usage.free / (1024 ** 3)


def get_response_time_ms(
    url: str, timeout: float = 10.0
) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    if not url:
        return None, None, None

    start = time.perf_counter()
    try:
        resp = requests.get(url, timeout=timeout)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return elapsed_ms, resp.status_code, None
    except requests.RequestException as e:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return elapsed_ms, None, str(e)


def get_active_sessions() -> Tuple[Optional[int], Optional[str]]:
    system = platform.system().lower()

    if system == "linux" or system == "darwin":
        proc = _run_command(["who"])
        if not proc or proc.returncode != 0:
            return None, None
        count = len([
            line for line in proc.stdout.splitlines() 
            if line.strip()
        ])
        return count, "who"

    if system == "windows":
        proc = _run_command(["query", "user"])
        if not proc or proc.returncode != 0:
            return None, None
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if len(lines) <= 1:
            return 0, "query user"
        return len(lines) - 1, "query user"

    return None, None


def collect_metrics(args):
    if not hasattr(args, "response_url") or args.response_url is None:
        base = getattr(args, "url", "") or ""
        path = getattr(args, "path", "/") or "/"
        if base and path and not path.startswith("/"):
            path = f"/{path}"
        args.response_url = f"{base.rstrip('/')}{path}" if base else None

    cpu = get_cpu_percent(sample_interval=args.cpu_sample_interval)
    mem_used, mem_total = get_memory_mb()
    disk_free = get_disk_free_gb(args.disk_path)

    response_ms, response_status, response_error = get_response_time_ms(
        args.response_url,
        timeout=args.response_timeout,
    )

    sessions, sessions_source = get_active_sessions()

    data = {
        "timestamp": now(),
        "cpu_percent": round(cpu, 2) if cpu is not None else None,
        "memory_mb": round(mem_used, 2) if mem_used is not None else None,
        "memory_total_mb": round(mem_total, 2) if mem_total is not None else None,
        "disk_free_gb": round(disk_free, 2) if disk_free is not None else None,
        "response_ms": response_ms,
        "response_status": response_status,
        "response_error": response_error,
        "response_url": args.response_url,
        "active_sessions": sessions,
        "active_sessions_source": sessions_source,
    }

    return data


def _ensure_output_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _build_output_path(output_dir: str) -> str:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"metrics_{ts}.json"
    return os.path.join(output_dir, filename)


def _write_payload(payload, output_dir: str) -> str:
    output_dir = _ensure_output_dir(output_dir)
    path = _build_output_path(output_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def monitor_resources(args):
    interval = max(args.interval, 0.0)
    count = args.count

    if interval <= 0 or count == 1:
        payload = collect_metrics(args)
        if args.output_dir:
            _write_payload(payload, args.output_dir)
        if not args.quiet:
            print_output(payload, args.output)
        raise SystemExit(0)

    emitted = 0
    while True:
        payload = collect_metrics(args)
        if args.output_dir:
            _write_payload(payload, args.output_dir)
        if not args.quiet:
            if args.output == "json":
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print_output(payload, args.output)
        emitted += 1

        if count > 0 and emitted >= count:
            break

        time.sleep(interval)

    raise SystemExit(0)