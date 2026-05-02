import argparse
import os
import yaml
from pathlib import Path

from scripts.deploy import deploy_up, deploy_down, deploy_demo, deploy_status
from scripts.export_manager import ExportManager, ExportConfigurationError
from scripts.upload_xlsx import upload_batch
from scripts.utils import success, error
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
    if args.config:
        cfg_path = Path(args.config)
    else:
        cfg_path = Path(__file__).with_name("config.yaml")

    if not cfg_path.is_absolute():
        cfg_path = (Path.cwd() / cfg_path).resolve()

    if not cfg_path.exists():
        error(f"File not found at path {cfg_path}")

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        error("Invalid YAML file")

    return data, str(cfg_path.parent)


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

def _parse_kv_pairs(items):
    result = {}
    for item in items or []:
        if "=" not in item:
            error(f"Invalid --set value '{item}'. Expected KEY=VALUE")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            error(f"Invalid --set value '{item}'. Key is empty")
        result[key] = value
    return result


def export_run(args):
    manager = ExportManager(
        args.project_dir,
        getattr(args, "config_data", None),
        config_base_dir=getattr(args, "config_dir", None),
    )

    try:
        extra_context = _parse_kv_pairs(getattr(args, "set", []))
        if getattr(args, "mode", None):
            extra_context["mode"] = args.mode
        if getattr(args, "no_xlsx", False):
            extra_context["build_xlsx"] = False

        artifact = manager.run(args.source, **extra_context)
    except ExportConfigurationError as exc:
        error(str(exc))

    if not artifact.xlsx_path:
        error(f"Источник '{args.source}' не создал xlsx-файл")

    upload_config = {
        "url": args.url,
        "user": args.username,
        "pass": args.password,
    }

    try:
        upload_result = upload_batch(
            config=upload_config,
            file_path=artifact.xlsx_path,
            dir_path=None,
            dest=args.dest,
            custom_name=args.name,
            overwrite=args.overwrite,
        )
    except ValueError as e:
        error(str(e))

    if isinstance(upload_result, dict) and "error" in upload_result:
        error(upload_result["error"])

    success(upload_result, args.output)


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
    backup_create_parser.add_argument(
        "--components", nargs="+", default=["all"],
        choices=["all", "core", "data"],
        help="Components to backup (default: all)"
    )
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
    export.add_argument(
        "source",
        help="Source name (for example: gitlogger, lms_stepik, lms_moodle, or any future module)"
    )
    export.add_argument(
        "--mode",
        default=None,
        help="Source mode (for example: commits, issues, pull_requests, wikis...)"
    )
    export.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra context variables for templating in config. Can be repeated."
    )
    export.add_argument(
        "--no-xlsx",
        action="store_true",
        help="Disable automatic XLSX generation from CSV"
    )

    add_nextcloud_args(export)
    export.add_argument("--dest", default="/", help="Destination folder in Nextcloud")
    export.add_argument("--name", help="Custom file name in Nextcloud")
    export.add_argument("--overwrite", action="store_true", default=False)
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
        config_data, config_dir = load_config(args)
        args.config_data = config_data
        args.config_dir = config_dir
        print("Configuration loaded")
    else:
        args.config_data = None

    if args.command is not None:
        args.func(args)


if __name__ == "__main__":
    main()
