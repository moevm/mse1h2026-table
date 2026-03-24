import argparse
import datetime
import subprocess
from pathlib import Path
import csv

import requests

from scripts.upload_xlsx import upload_batch
from scripts.users_from_csv import create_users_from_csv
from scripts.utils import success, error, now
from scripts.users import (
    users_create,
    users_delete,
    users_csv_create,
    users_csv_delete,
    users_list,
)


def add_nextcloud_args(parser):
    parser.add_argument(
        "--url", default="http://localhost:8080", help="Nextcloud URL"
    )

    parser.add_argument(
        "--username", default="admin", help="Admin username"
    )

    parser.add_argument(
        "--password", default="super_secure_password", help="Admin password"
    )


def get_compose_dir(args):
    return (Path(__file__).resolve().parent.parent /
            "playground" /
            "onlyoffice-nextcloud" /
            "deploy").resolve()


def get_compose_file(args):
    return get_compose_dir(args) / "docker-compose.yml"


def get_scripts_dir():
    return Path(__file__).resolve().parent / "scripts"


def get_nextcloud_url(args):
    return getattr(args, "url", "http://localhost:8080")


def get_admin_user(args):
    return getattr(args, "username", "admin")


def get_admin_password(args):
    return getattr(args, "password", "super_secure_password")


def run_command(cmd, cwd=None):
    try:
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
        msg = e.stderr.strip() if e.stderr else e.stdout.strip()
        if not msg:
            msg = str(e)
        error(msg)


# DEPLOY

def deploy_up(args):
    # deploy up
    print("[STUB] docker compose up -d")
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    run_command(["docker", "compose", "-f", str(compose_file),
                "up", "-d"], cwd=compose_dir)

    success({
        "services": [
            "app", "db", "onlyoffice-document-server",
            "nginx", "nextcloud-init"
        ],
        "status": "running",
        "timestamp": now(),
        "env": args.env,
        "project_dir": args.project_dir
    }, args.output)


def deploy_down(args):
    # deploy down
    print("[STUB] docker compose down")
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    run_command(["docker", "compose", "-f",
                str(compose_file), "down"], cwd=compose_dir)

    success({
        "status": "stopped",
        "timestamp": now()
    }, args.output)


def deploy_status(args):
    # deploy status
    success({
        "tables": "running",
        "forms": "running"
    }, args.output)


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
        print(f"\n=== {title} ===")

    def print_kv(key, value):
        print(f"{key}: {value}")

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

    def share_folder(share_type, share_with, permissions):
        url = (
            f"{base_url.rstrip('/')}/ocs/v2.php/apps/files_sharing/"
            "api/v1/shares?format=json"
        )
        resp = requests.post(
            url,
            auth=(admin_user, admin_pass),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data={
                "path": folder_name,
                "shareType": str(share_type),
                "shareWith": share_with,
                "permissions": str(permissions),
            },
            timeout=30,
        )

        if resp.status_code != 200:
            return {"status": "error", "http_code":
                    resp.status_code, "body": resp.text[:300]}

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
        print("Failed users:")
        for item in result_users["failed"]:
            print(
                f"- {item.get('user')}: code={item.get('code')}, "
                f"reason={item.get('reason')}"
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
                f"({permissions_text(u['permissions'])})"
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
        print(f"- uploaded: {xlsx_file.name}")

    print_section("SHARES")
    share_results = []
    for group_name, permissions in [
        ("staff", 31),
        ("teachers", 15),
        ("students", 1),
        ("guests", 1),
        ("support", 1),
    ]:
        share_result = share_folder(1, group_name, permissions)
        share_results.append({
            "group": group_name,
            "permissions": permissions,
            "result": share_results
        })

        if share_result.get("status") == "shared":
            print(f"- {group_name}: OK")
        else:
            print(
                f"- {group_name}: FAIL "
                f"(code={share_result.get('code')}, "
                f"http_code={share_result.get('http_code')}, "
                f"reason={share_result.get('reason')})"
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


# BACKUP

def backup_create(args):
    # backup create
    backup_id = f"backup-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    print("[STUB] Creating backup")
    success({
        "backup_id": backup_id,
        "status": "created",
        "timestamp": now()
    }, args.output)


def backup_list(args):
    # backup list
    success({
        "backups": [
            {"id": "backup-20260220010101", "size": "120MB"},
            {"id": "backup-20260221010101", "size": "130MB"}
        ]
    }, args.output)


def backup_restore(args):
    # backup restore [backup_id]
    print(f"[STUB] Restoring backup {args.backup_id}")
    success({
        "backup_id": args.backup_id,
        "status": "restored"
    }, args.output)


# MONITOR

def monitor_status(args):
    # monitor status
    success({
        "overall": "OK",
        "tables": {"status": "ok", "response_ms": 210},
        "forms": {"status": "ok", "response_ms": 150}
    }, args.output)


def monitor_resources(args):
    # monitor resources
    success({
        "cpu_percent": 32,
        "memory_mb": 1024,
        "disk_free_gb": 120
    }, args.output)


# LOADTEST

def loadtest_run(args):
    # loadtest run --users N
    print("[STUB] Running load test simulation")
    success({
        "simulated_users": args.users,
        "avg_response_ms": 320,
        "errors": 0
    }, args.output)


# EXPORT

def export_run(args):
    # export [module]
    print(f"[STUB] Running export module: {args.module}")
    success({
        "module": args.module,
        "status": "completed",
        "rows_exported": 120
    }, args.output)


# UPLOAD

def upload_run(args):
    """
    Запуск процесса загрузки таблиц.
    """
    config = {
        "url": args.url,
        "user": args.username,
        "pass": args.password
    }
    try:
        results = upload_batch(
            config=config,
            file_path=args.file,
            dir_path=args.dir,
            dest=args.dest,
            custom_name=args.name,
            overwrite=args.overwrite
        )
    except ValueError as e:
        error(str(e))

    if isinstance(results, dict) and "error" in results:
        error(results["error"])

    success(results, args.output)


# CLI Definition

def main():
    parser = argparse.ArgumentParser()

    # Global flags
    parser.add_argument("--output", choices=["text", "json"], default="text")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--env", help="Env")
    parser.add_argument("--project-dir", default=".", help="Project directory")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # DEPLOY
    deploy = subparsers.add_parser("deploy")
    add_nextcloud_args(deploy)
    deploy_sub = deploy.add_subparsers(dest="action", required=True)

    deploy_sub.add_parser("up").set_defaults(func=deploy_up)
    deploy_sub.add_parser("down").set_defaults(func=deploy_down)
    deploy_sub.add_parser("status").set_defaults(func=deploy_status)
    deploy_sub.add_parser("demo").set_defaults(func=deploy_demo)

    # USERS
    users = subparsers.add_parser("users")
    users_sub = users.add_subparsers(dest="action", required=True)

    # Single user
    create = users_sub.add_parser("create")
    create.add_argument("user")
    create.set_defaults(func=users_create)

    delete = users_sub.add_parser("delete")
    delete.add_argument("user")
    delete.set_defaults(func=users_delete)

    # Users from csv
    csv_create = users_sub.add_parser("csv-create")
    csv_create.add_argument("csv_file", help="Full path to CSV file")
    add_nextcloud_args(csv_create)
    csv_create.set_defaults(func=users_csv_create)

    csv_delete = users_sub.add_parser("csv-delete")
    csv_delete.add_argument("csv_file", help="Full path to CSV file")
    add_nextcloud_args(csv_delete)
    csv_delete.set_defaults(func=users_csv_delete)

    # List users
    list_parser = users_sub.add_parser("list")
    list_parser.add_argument("--prefix", help="Filter by prefix", default=None)
    list_parser.add_argument("--details", action="store_true",
                             help="Show detailed user info")
    list_parser.add_argument(
        "--filter", nargs=3, action="append",
        metavar=("FIELD", "MODE", "VALUE"),
        help="Universal filter: <field> <mode> <value>. "
             "Mode: contains|prefix|exact. Field: username|email|group"
    )

    add_nextcloud_args(list_parser)
    list_parser.set_defaults(func=users_list)

    # BACKUP
    backup = subparsers.add_parser("backup")
    backup_sub = backup.add_subparsers(dest="action", required=True)

    backup_sub.add_parser("create").set_defaults(func=backup_create)
    backup_sub.add_parser("list").set_defaults(func=backup_list)

    restore = backup_sub.add_parser("restore")
    restore.add_argument("backup_id")
    restore.set_defaults(func=backup_restore)

    # MONITOR
    monitor = subparsers.add_parser("monitor")
    monitor_sub = monitor.add_subparsers(dest="action", required=True)

    monitor_sub.add_parser("status").set_defaults(func=monitor_status)
    monitor_sub.add_parser("resources").set_defaults(func=monitor_resources)

    # LOADTEST
    loadtest = subparsers.add_parser("loadtest")
    loadtest_sub = loadtest.add_subparsers(dest="action", required=True)

    run = loadtest_sub.add_parser("run")
    run.add_argument("--users", type=int, required=True)
    run.set_defaults(func=loadtest_run)

    # EXPORT
    export = subparsers.add_parser("export")
    export.add_argument("module", choices=["gitlogger", "lms"])
    export.set_defaults(func=export_run)

    # UPLOAD
    upload = subparsers.add_parser("upload", help="Upload .xlsx tables")
    source_group = upload.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", help="Path to single file")
    source_group.add_argument("--dir", help="Path to directory for batch")
    upload.add_argument("--dest", default="/", help="Destination folder")
    upload.add_argument("--name", help="Custom name (for --file only)")
    upload.add_argument("--overwrite", action="store_true", default=False)
    add_nextcloud_args(upload)
    upload.set_defaults(func=upload_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
