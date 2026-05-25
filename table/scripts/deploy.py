import csv
import json
import subprocess
import sys
import time
import os
from pathlib import Path

import requests

from scripts.nextcloud_client import NextcloudClient
from scripts.upload_xlsx import upload_batch
from scripts.users_from_csv import create_users_from_csv
from scripts.utils import success, error, now


def get_compose_dir(args):
    repo_root = Path(__file__).resolve().parent.parent.parent
    return (repo_root / "deploy").resolve()


def get_compose_file(args):
    return get_compose_dir(args) / "docker-compose.yml"


def get_scripts_dir():
    return Path(__file__).resolve().parent


def _first_non_empty(*values):
    for value in values:
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def get_nextcloud_url(args):
    return _first_non_empty(
        getattr(args, "url", None),
        os.environ.get("NEXTCLOUD_URL"),
        os.environ.get("CLI_NEXTCLOUD_URL"),
    ) or error("Не задан Nextcloud URL: ожидается --url или NEXTCLOUD_URL / CLI_NEXTCLOUD_URL")


def get_admin_user(args):
    return _first_non_empty(
        getattr(args, "username", None),
        os.environ.get("NEXTCLOUD_ADMIN_USER"),
    ) or error("Не задан NEXTCLOUD_ADMIN_USER")


def get_admin_password(args):
    return _first_non_empty(
        getattr(args, "password", None),
        os.environ.get("NEXTCLOUD_ADMIN_PASSWORD"),
    ) or error("Не задан NEXTCLOUD_ADMIN_PASSWORD")


def get_public_nextcloud_url(compose_dir):
    """URL Nextcloud для браузера, собранный из deploy/.env или env.

    Это внешний URL вида http://<NEXTCLOUD_HOSTNAME>:<NEXTCLOUD_PORT>.
    """
    host = _first_non_empty(
        os.environ.get("NEXTCLOUD_HOSTNAME"),
        get_env_param(compose_dir, "NEXTCLOUD_HOSTNAME"),
    )
    port = _first_non_empty(
        os.environ.get("NEXTCLOUD_PORT"),
        get_env_param(compose_dir, "NEXTCLOUD_PORT"),
    )

    if not host or not port:
        error("Не заданы NEXTCLOUD_HOSTNAME / NEXTCLOUD_PORT")

    return f"http://{host}:{port}"


def run_command(cmd, cwd=None, stream=False):
    try:
        if stream:
            # Прогресс docker compose проксируем в stderr родителя:
            # пользователь видит pull/start, stdout остаётся чистым под
            # финальный JSON для --output json.
            return subprocess.run(
                cmd,
                cwd=cwd,
                check=True,
                stdout=sys.stderr,
                stderr=sys.stderr,
            )
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,
            text=True,
            capture_output=True
        )
    except FileNotFoundError as e:
        error(str(e))
    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or "").strip() if e.stderr else ""
        stdout_text = (e.stdout or "").strip() if e.stdout else ""
        msg = stderr_text or stdout_text or str(e)
        error(msg)


def permissions_text(permissions):
    permissions = int(permissions)
    flags = [
        (1, "read"),
        (2, "update"),
        (4, "create"),
        (8, "delete"),
        (16, "share"),
    ]
    parts = [name for bit, name in flags if permissions & bit]
    return ", ".join(parts) if parts else "none"


def resolve_role_and_permissions(login, groups):
    groups = set(groups or [])
    if login == "teacher_head" or "admin" in groups:
        return "owner", 31
    if login == "teacher_math" or "teachers" in groups:
        return "editor", 15
    if "students" in groups or login.startswith("student_"):
        return "reader", 1
    if "guests" in groups or "guest" in login:
        return "reader", 1
    if "support" in groups or login.startswith("support"):
        return "reader", 1
    return "reader", 1


def read_users_csv(csv_path):
    with open(csv_path, mode="r", encoding="utf-8", newline="") as f:
        return [
            {
                "login": (row.get("login") or "").strip(),
                "password": (row.get("password") or "").strip(),
                "groups": [
                    g.strip()
                    for g in (row.get("groups") or "").split(",")
                    if g.strip()
                ],
            }
            for row in csv.DictReader(f)
        ]


def share_folder(client, folder_name, share_type, share_with, permissions):
    url = (
        f"{client.base_url}/ocs/v2.php/apps/files_sharing/"
        "api/v1/shares?format=json"
    )
    resp = client.session.post(
        url,
        data={
            "path": folder_name,
            "shareType": str(share_type),
            "shareWith": share_with,
            "permissions": str(permissions),
        },
        timeout=30,
    )

    if resp.status_code != 200:
        return {
            "status": "error",
            "http_code": resp.status_code,
            "body": resp.text[:300]
        }

    try:
        data = resp.json()
    except ValueError:
        return {
            "status": "error",
            "reason": "Invalid JSON response from share API",
            "body": resp.text[:300]
        }

    meta = data.get("ocs", {}).get("meta", {})
    code = meta.get("statuscode")
    message = meta.get("message", "")

    if code in (100, 200):
        return {
            "status": "shared",
            "permissions": permissions,
            "share_with": share_with,
            "message": message
        }

    return {
        "status": "error",
        "code": code,
        "reason": message,
        "share_with": share_with,
        "permissions": permissions
    }


def deploy_up(args):
    # deploy up
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    run_command(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        cwd=compose_dir,
        stream=True,
    )

    success({
        "services": [
            "app", "db", "onlyoffice-document-server",
            "nginx", "nextcloud-init", "cron-worker",
        ],
        "status": "running",
        "timestamp": now(),
    }, args.output)


def deploy_down(args):
    # deploy down
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    run_command(
        ["docker", "compose", "-f", str(compose_file), "down", "--remove-orphans"],
        cwd=compose_dir,
        stream=True,
    )

    success({
        "status": "stopped",
        "timestamp": now()
    }, args.output)


def deploy_status(args):
    # deploy status
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    base_url = get_nextcloud_url(args)

    client = NextcloudClient(
        base_url,
        get_admin_user(args),
        get_admin_password(args)
    )

    def overall_status(components):
        values = [c.get("status", "error") for c in components.values()]
        if any(v == "error" for v in values):
            return "error"
        if any(v == "starting" for v in values):
            return "starting"
        return "ok"

    def parse_compose_ps():
        result = run_command(
            [
                "docker", "compose", "-f", str(compose_file),
                "ps", "--format", "json", "--all"
            ],
            cwd=compose_dir
        )

        containers = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue

            service = item.get("Service") or item.get("service")
            if service:
                containers[service] = item
        return containers

    def container_state(item):
        service = item.get("Service")
        state = (item.get("State") or "").lower()
        health = (item.get("Health") or "").lower()
        exit_code = str(item.get("ExitCode", "")).strip()

        if service == "nextcloud-init":
            if exit_code == "0":
                return "ok"
            if state in ("exited", "dead") and exit_code != "0":
                return "error"
            return "starting"

        if state == "running":
            if health == "unhealthy":
                return "error"
            if health == "starting":
                return "starting"
            return "ok"

        if state in ("created", "starting", "restarting"):
            return "starting"

        if state in ("exited", "dead"):
            return "error"

        return "error"

    def check_db():
        cmd = [
            "docker", "compose", "-f", str(compose_file),
            "exec", "-T", "db",
            "sh", "-lc",
            'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
        ]
        proc = subprocess.run(
            cmd,
            cwd=compose_dir,
            text=True,
            capture_output=True
        )

        if proc.returncode == 0:
            return {
                "status": "ok",
                "output": proc.stdout.strip() or proc.stderr.strip()
            }

        if proc.returncode == 1:
            return {
                "status": "starting",
                "output": proc.stdout.strip() or proc.stderr.strip()
            }

        return {
            "status": "error",
            "output": (
                proc.stdout.strip() or
                proc.stderr.strip() or
                "pg_isready failed"
            )
        }

    def check_nextcloud():
        try:
            resp = client.session.get(
                f"{client.base_url}/status.php",
                timeout=30
            )

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except ValueError:
                    return {
                        "status": "starting",
                        "http_code": 200,
                        "reason": "status.php returned non-JSON"
                    }

                if (data.get("installed") is True and
                        not data.get("maintenance", False)):
                    return {
                        "status": "ok",
                        "http_code": 200,
                        "installed": True,
                        "maintenance": False,
                        "version": data.get("version"),
                        "versionstring": data.get("versionstring"),
                    }

                return {
                    "status": "starting",
                    "http_code": 200,
                    "installed": data.get("installed"),
                    "maintenance": data.get("maintenance"),
                }

            if resp.status_code in (502, 503, 504):
                return {
                    "status": "starting",
                    "http_code": resp.status_code
                }

            return {
                "status": "error",
                "http_code": resp.status_code,
                "reason": resp.text[:200]
            }

        except requests.RequestException as e:
            return {
                "status": "starting",
                "reason": str(e)
            }

    def check_http_service(name, url, paths):
        last = None
        for path in paths:
            try:
                resp = requests.get(
                    f"{url.rstrip('/')}{path}",
                    timeout=20,
                    allow_redirects=False
                )

                if resp.status_code in (200, 301, 302, 401, 403):
                    return {
                        "status": "ok",
                        "http_code": resp.status_code,
                        "path": path
                    }

                if resp.status_code in (502, 503, 504):
                    last = {
                        "status": "starting",
                        "http_code": resp.status_code,
                        "path": path
                    }
                else:
                    last = {
                        "status": "error",
                        "http_code": resp.status_code,
                        "path": path,
                        "reason": resp.text[:200]
                    }

            except requests.RequestException as e:
                last = {
                    "status": "starting",
                    "path": path,
                    "reason": str(e)
                }

        return last or {
            "status": "error",
            "reason": f"{name} is unreachable"
        }

    def collect_status():
        containers_raw = parse_compose_ps()

        required_container_names = [
            "app", "db", "onlyoffice-document-server", "nginx",
            "cron-worker"
        ]
        optional_container_names = ["nextcloud-init"]
        all_container_names = (
            required_container_names + optional_container_names
        )

        containers = {}
        for name in all_container_names:
            item = containers_raw.get(name)
            if not item:
                if name == "nextcloud-init":
                    containers[name] = {
                        "status": "ok",
                        "state": "exited",
                        "health": "",
                        "service": name,
                        "note": "one-shot init container"
                    }
                else:
                    containers[name] = {
                        "status": "error",
                        "reason": "container not found",
                        "service": name
                    }
            else:
                containers[name] = {
                    "status": container_state(item),
                    "state": item.get("State"),
                    "health": item.get("Health"),
                    "service": name,
                }

        db_status = check_db()
        nextcloud_status = check_nextcloud()
        nginx_status = check_http_service("nginx", base_url, ["/"])

        required_containers_status = overall_status({
            name: {"status": containers[name]["status"]}
            for name in required_container_names
        })

        components = {
            "containers": {
                "status": overall_status({
                    name: {"status": containers[name]["status"]}
                    for name in all_container_names
                }),
                "required_status": required_containers_status,
                "items": containers
            },
            "db": db_status,
            "nextcloud": nextcloud_status,
            "nginx": nginx_status,
        }

        overall = overall_status({
            "containers": {"status": required_containers_status},
            "db": {"status": db_status["status"]},
            "nextcloud": {"status": nextcloud_status["status"]},
            "nginx": {"status": nginx_status["status"]},
        })

        return {
            "overall": overall,
            "nextcloud_url": get_public_nextcloud_url(compose_dir),
            "polled_url": base_url,
            "components": components,
            "timestamp": now(),
        }

    deadline = time.time() + max(args.timeout, 1)
    attempts = 0
    snapshot = None

    while True:
        attempts += 1
        snapshot = collect_status()
        snapshot["attempts"] = attempts
        snapshot["wait"] = {
            "enabled": bool(args.wait),
            "timeout": args.timeout,
            "interval": args.interval,
        }

        if not args.wait or snapshot["overall"] == "ok":
            break

        if time.time() >= deadline:
            snapshot["wait"]["timed_out"] = True
            break

        time.sleep(max(args.interval, 1))

    success(snapshot, args.output)


def deploy_demo(args):
    # deploy demo
    compose_file = get_compose_file(args)
    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    base_url = get_nextcloud_url(args)
    admin_user = get_admin_user(args)
    admin_pass = get_admin_password(args)
    scripts_dir = get_scripts_dir()
    folder_name = "Учебные_таблицы"

    def print_section(title):
        print(f"\n=== {title} ===", file=sys.stderr)

    def print_kv(key, value):
        print(f"{key}: {value}", file=sys.stderr)

    print_section("DEPLOY DEMO")
    print_kv("nextcloud_url", base_url)
    print_kv("admin_user", admin_user)
    print_kv("scripts_dir", str(scripts_dir))

    users_csv = scripts_dir / "users_example.csv"
    if not users_csv.exists():
        error(f"Не найден файл пользователей: {users_csv}")

    users_rows = read_users_csv(users_csv)
    result_users = create_users_from_csv(
        str(users_csv), base_url, admin_user, admin_pass
    )

    if "error" in result_users:
        error(result_users["error"])

    created_set = set(result_users.get("created", []))
    failed_map = {
        item.get("user"): item
        for item in result_users.get("failed", [])
        if item.get("user")
    }

    print_section("USERS")
    print_kv("total", result_users.get("total"))
    print_kv("created", len(result_users.get("created", [])))
    print_kv("failed", len(result_users.get("failed", [])))
    print_kv("groups_created", len(result_users.get("groups_created", [])))

    if result_users.get("failed"):
        print("Failed users:", file=sys.stderr)
        for item in result_users["failed"]:
            print(
                f"- {item.get('user')}: code={item.get('code')}, "
                f"reason={item.get('reason')}",
                file=sys.stderr,
            )

    debug_users = []
    for row in users_rows:
        role, permissions = resolve_role_and_permissions(
            row["login"],
            row["groups"]
        )

        item = {
            "login": row["login"],
            "password": row["password"],
            "groups": row["groups"],
            "role": role,
            "permissions": permissions,
            "created": row["login"] in created_set,
        }
        if row["login"] in failed_map:
            item["failed"] = failed_map[row["login"]]
        debug_users.append(item)

    print_section("ROLES")
    for u in debug_users:
        if u["created"]:
            print(
                f"- {u['login']}: {u['role']} "
                f"({permissions_text(u['permissions'])})",
                file=sys.stderr,
            )

    xlsx_files = sorted(scripts_dir.glob("*.xlsx"))
    if not xlsx_files:
        error(f"Не найдены .xlsx файлы в папке: {scripts_dir}")

    print_section("TABLES")
    tables = []
    for xlsx_file in xlsx_files:
        try:
            xlsx_upload = upload_batch(
                config={
                    "url": base_url,
                    "user": admin_user,
                    "pass": admin_pass
                },
                file_path=str(xlsx_file),
                dest=f"/{folder_name}",
                overwrite=True,
            )
        except ValueError as e:
            error(str(e))

        if isinstance(xlsx_upload, dict) and "error" in xlsx_upload:
            error(xlsx_upload["error"])

        tables.append({"source": str(xlsx_file), "result": xlsx_upload})
        print(f"- uploaded: {xlsx_file.name}", file=sys.stderr)

    print_section("SHARES")
    share_results = []
    client = NextcloudClient(base_url, admin_user, admin_pass)

    for group_name, permissions in [
        ("staff", 31),
        ("teachers", 15),
        ("students", 1),
        ("guests", 1),
        ("support", 1),
    ]:
        share_result = share_folder(
            client, folder_name, 1, group_name, permissions
        )
        share_results.append({
            "group": group_name,
            "permissions": permissions,
            "result": share_result
        })

        if share_result.get("status") == "shared":
            print(f"- {group_name}: OK", file=sys.stderr)
        else:
            print(
                f"- {group_name}: FAIL "
                f"(code={share_result.get('code')}, "
                f"http_code={share_result.get('http_code')}, "
                f"reason={share_result.get('reason')})",
                file=sys.stderr,
            )

    success({
        "status": "demo_loaded",
        "timestamp": now(),
        "nextcloud_url": base_url,
        "users": result_users,
        "debug_users": debug_users,
        "shares": share_results,
        "tables": tables,
    }, args.output)
