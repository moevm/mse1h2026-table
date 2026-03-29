import argparse
import datetime
import os
import yaml

from scripts.deploy import deploy_up, deploy_down, deploy_demo, deploy_status
from scripts.upload_xlsx import upload_batch
from scripts.utils import success, error, now
from scripts.users import (
    users_create,
    users_delete,
    users_csv_create,
    users_csv_delete,
    users_list,
)
from scripts.backup import backup_create, backup_list


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


def load_config(args):
    # --config [path]
    cfg_path = args.config
    if not os.path.exists(cfg_path):
        error(f"File not found at path {cfg_path}")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        error("Invalid YAML file")

    return data


# BACKUP

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

    subparsers = parser.add_subparsers(dest="command")

    # DEPLOY
    deploy = subparsers.add_parser("deploy")
    add_nextcloud_args(deploy)
    deploy_sub = deploy.add_subparsers(dest="action", required=True)

    deploy_sub.add_parser("up").set_defaults(func=deploy_up)
    deploy_sub.add_parser("down").set_defaults(func=deploy_down)
    deploy_sub.add_parser("demo").set_defaults(func=deploy_demo)

    # STATUS
    status = deploy_sub.add_parser("status")
    status.add_argument("--wait", action="store_true",
                        help="Wait until the whole system is ready")
    status.add_argument("--timeout", type=int, default=1200,
                        help="Max wait time in seconds")
    status.add_argument("--interval", type=int, default=10,
                        help="Retry interval in seconds")
    status.set_defaults(func=deploy_status)

    # USERS
    users = subparsers.add_parser("users")
    users_sub = users.add_subparsers(dest="action", required=True)

    # Single user
    create = users_sub.add_parser("create")
    create.add_argument("user")
    create.add_argument(
        "--email", default=None,
        help="User email"
    )
    create.add_argument(
        "--display-name", dest="display_name",
        default=None, help="Display name"
    )
    create.add_argument(
        "--user-password", dest="user_password",
        default=None, help="User password"
    )
    create.add_argument(
        "--quota", default=None,
        help="Storage quota (e.g. 1GB)"
    )
    create.add_argument(
        "--groups", nargs="+", default=None,
        help="Groups to add user to"
    )
    add_nextcloud_args(create)
    create.set_defaults(func=users_create)

    delete = users_sub.add_parser("delete")
    delete.add_argument("user")
    add_nextcloud_args(delete)
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

    backup_create_parser = backup_sub.add_parser("create")
    backup_create_parser.add_argument("--exclude-db", action="store_true", help="Exclude database dump")
    backup_create_parser.add_argument("--exclude-data", action="store_true", help="Exclude data folder archive")
    backup_create_parser.add_argument("--name", help="Optional backup name")
    backup_create_parser.set_defaults(func=backup_create)

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

    if args.config:
        config_data = load_config(args)
        args.config_data = config_data
        print("Configuration loaded")
    else:
        args.config_data = None

    if args.command is not None:
        args.func(args)


if __name__ == "__main__":
    main()
