import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.deploy import (
    get_compose_dir,
    get_public_nextcloud_url,
)
from scripts.utils import success, error, now


def _find_locust():
    # venv может быть не в PATH при запуске через `.venv/bin/python manage.py`
    candidate = Path(sys.executable).parent / "locust"
    if candidate.exists():
        return str(candidate)
    return shutil.which("locust")


_SCENARIOS = {
    "stepped": "table/loadtest/scenarios/stepped.py",
    "smoke": "table/loadtest/scenarios/smoke.py",
}


def _repo_root():
    return Path(__file__).resolve().parent.parent.parent


def _scenario_path(name):
    if name not in _SCENARIOS:
        error(
            f"Unknown scenario '{name}'. "
            f"Available: {', '.join(sorted(_SCENARIOS))}"
        )
    path = (_repo_root() / _SCENARIOS[name]).resolve()
    if not path.exists():
        error(f"Scenario file not found: {path}")
    return path


def _parse_locust_stats(stats_csv):
    if not stats_csv.exists():
        return None

    with stats_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Name") != "Aggregated":
                continue

            def num(key, cast=float, default=0):
                v = row.get(key, "")
                try:
                    return cast(v) if v != "" else default
                except (TypeError, ValueError):
                    return default

            return {
                "total_requests": num("Request Count", int),
                "failures": num("Failure Count", int),
                "avg_ms": num("Average Response Time"),
                "median_ms": num("Median Response Time"),
                "min_ms": num("Min Response Time"),
                "max_ms": num("Max Response Time"),
                "p95_ms": num("95%"),
                "p99_ms": num("99%"),
                "rps": num("Requests/s"),
            }
    return None


def loadtest_run(args):
    locust_bin = _find_locust()
    if locust_bin is None:
        error(
            "locust not found. Install with: "
            "pip install -r table/loadtest/requirements.txt"
        )

    scenario_path = _scenario_path(args.scenario)

    if args.host:
        host = args.host
    else:
        compose_dir = get_compose_dir(args)
        host = get_public_nextcloud_url(compose_dir)

    if args.results_dir:
        results_dir = Path(args.results_dir).resolve()
    else:
        timestamp = now().replace(":", "-").split(".")[0]
        results_dir = (
            _repo_root() / "table" / "loadtest" / "results" / timestamp
        )
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_prefix = results_dir / "stats"
    html_report = results_dir / "report.html"

    cmd = [
        locust_bin,
        "-f", str(scenario_path),
        "--host", host,
        "--headless",
        "--csv", str(csv_prefix),
        "--html", str(html_report),
        "--exit-code-on-error", "0",
    ]
    if args.users is not None:
        cmd += ["--users", str(args.users)]
    if args.spawn_rate is not None:
        cmd += ["--spawn-rate", str(args.spawn_rate)]
    if args.run_time:
        cmd += ["--run-time", args.run_time]

    env = os.environ.copy()
    if args.password:
        env["LOADTEST_PASSWORD"] = args.password
    if args.user_prefix:
        env["LOADTEST_USER_PREFIX"] = args.user_prefix
    if args.user_max is not None:
        env["LOADTEST_USER_MAX"] = str(args.user_max)

    proc = subprocess.run(cmd, env=env)

    stats = _parse_locust_stats(results_dir / "stats_stats.csv")

    result = {
        "scenario": args.scenario,
        "host": host,
        "results_dir": str(results_dir),
        "html_report": str(html_report) if html_report.exists() else None,
        "exit_code": proc.returncode,
        "stats": stats,
    }

    if proc.returncode != 0:
        error(
            f"locust exited with code {proc.returncode}. "
            f"See {results_dir}"
        )

    success(result, args.output)
