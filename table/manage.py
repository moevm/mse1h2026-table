import argparse
import sys
import json
import datetime
import os

from scripts.upload_xlsx import upload_batch

from scripts.users_from_csv import create_users_from_csv, delete_users_from_csv


def print_output(data, fmt="text"):
    if fmt == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}")
        else:
            print(data)


def success(data=None, fmt="text"):
    if data:
        print_output(data, fmt)
    sys.exit(0)


def error(message, code=1):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def now():
    return datetime.datetime.now().isoformat()


# DEPLOY

def deploy_up(args):
    # deploy up
    print("[STUB] docker compose up -d")
    success({
        "services": ["tables", "forms"],
        "status": "running",
        "timestamp": now(),
        "env": args.env,
        "project_dir": args.project_dir
    }, args.output)


def deploy_down(args):
    # deploy down
    print("[STUB] docker compose down")
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


# USERS

def users_create(args):
    # users create [user]
    print(f"[STUB] Creating user: {args.user}")
    success({
        "username": args.user,
        "status": "created",
        "timestamp": now()
    }, args.output)


def users_delete(args):
    # users delete [user]
    print(f"[STUB] Deleting user: {args.user}")
    success({
        "username": args.user,
        "status": "deleted"
    }, args.output)


def users_csv_create(args):
    # users csv-create [csv_file] --flags
    print(f"Starting csv user creation from: {args.csv_file}")
    print(f"Target: {args.url} (User: {args.username})")

    result = create_users_from_csv(
        args.csv_file,
        args.url,
        args.username,
        args.password
    )

    # Если в результате есть ошибки уровня скрипта (не API), выводим их
    if "error" in result:
        error(result["error"])

    success(result, args.output)


def users_csv_delete(args):
    # users csv-delete [csv_file] --flags
    print(f"Starting csv user deletion based on: {args.csv_file}")
    print(f"Target: {args.url} (User: {args.username})")

    result = delete_users_from_csv(
        args.csv_file,
        args.url,
        args.username,
        args.password
    )

    if "error" in result:
        error(result["error"])

    success(result, args.output)


def users_list(args):
    from scripts.nextcloud_api import get_nextcloud_users, \
        get_nextcloud_user_details

    base_url = args.url
    admin_user = args.username
    admin_pass = args.password

    try:
        users = get_nextcloud_users(base_url, admin_user, admin_pass)

        if getattr(args, "prefix", None):
            users = [u for u in users if u.startswith(args.prefix)]

        need_details = bool(args.filter) or getattr(args, "details", False)
        users_list = []
        for u in users:
            details = None
            if need_details:
                details = get_nextcloud_user_details(
                    base_url, admin_user, admin_pass, u
                )

            passed = True
            if args.filter:
                for field, mode, value in args.filter:
                    v = None
                    if field == "username":
                        v = u if not details else details.get("username")
                    elif field == "email":
                        v = details.get("email") if details else None
                    elif field == "group":
                        v = details.get("groups") if details else []
                    else:
                        passed = False
                        break

                    if mode == "contains":
                        if field == "group":
                            if value not in (v or []):
                                passed = False
                                break
                        elif not v or value not in v:
                            passed = False
                            break

                    elif mode == "prefix":
                        if field == "group":
                            if not any(g.startswith(value) for g in (v or [])):
                                passed = False
                                break
                        elif not v or not v.startswith(value):
                            passed = False
                            break

                    elif mode == "exact":
                        if field == "group":
                            if value not in (v or []):
                                passed = False
                                break
                        elif not v or v != value:
                            passed = False
                            break
                    else:
                        passed = False
                        break

            if not passed:
                continue

            if getattr(args, "details", False):
                if not details:
                    details = get_nextcloud_user_details(
                        base_url, admin_user, admin_pass, u
                    )
                users_list.append(details)
            else:
                users_list.append(u)

        success({"users": users_list}, args.output)

    except Exception as e:
        error(f"Failed to fetch users: {e}")


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
    deploy_sub = deploy.add_subparsers(dest="action", required=True)

    deploy_sub.add_parser("up").set_defaults(func=deploy_up)
    deploy_sub.add_parser("down").set_defaults(func=deploy_down)
    deploy_sub.add_parser("status").set_defaults(func=deploy_status)

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
    csv_create.add_argument("--url", default=os.environ.get(
        "NEXTCLOUD_URL", "http://localhost"), help="Nextcloud API URL")
    csv_create.add_argument("--username", default=os.environ.get(
        "NEXTCLOUD_ADMIN_USER", "admin"), help="Admin username")
    csv_create.add_argument("--password", default=os.environ.get(
        "NEXTCLOUD_ADMIN_PASSWORD", "super_secure_password"),
        help="Admin password")
    csv_create.set_defaults(func=users_csv_create)

    csv_delete = users_sub.add_parser("csv-delete")
    csv_delete.add_argument("csv_file", help="Full path to CSV file")
    csv_delete.add_argument("--url", default=os.environ.get(
        "NEXTCLOUD_URL", "http://localhost"), help="Nextcloud API URL")
    csv_delete.add_argument("--username", default=os.environ.get(
        "NEXTCLOUD_ADMIN_USER", "admin"), help="Admin username")
    csv_delete.add_argument("--password", default=os.environ.get(
        "NEXTCLOUD_ADMIN_PASSWORD", "super_secure_password"),
        help="Admin password")
    csv_delete.set_defaults(func=users_csv_delete)

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
    
    list_parser.add_argument("--url", default=os.environ.get(
        "NEXTCLOUD_URL", "http://nextcloud.local:8080"), help="Nextcloud API URL")
    list_parser.add_argument("--username", default=os.environ.get(
        "NEXTCLOUD_ADMIN_USER", "admin"), help="Admin username")
    list_parser.add_argument("--password", default=os.environ.get(
        "NEXTCLOUD_ADMIN_PASSWORD", "super_secure_password"),
        help="Admin password")
    
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
    upload.add_argument("--overwrite", action="store_true", default=False,
                        help="Overwrite existing files")
    upload.add_argument("--url", default=os.environ.get(
        "NEXTCLOUD_URL", "http://localhost"), help="Nextcloud URL")
    upload.add_argument("--username", default=os.environ.get(
        "NEXTCLOUD_ADMIN_USER", "admin"), help="Admin username")
    upload.add_argument("--password", default=os.environ.get(
        "NEXTCLOUD_ADMIN_PASSWORD", "super_secure_password"),
        help="Admin password")
    upload.set_defaults(func=upload_run)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
