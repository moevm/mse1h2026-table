import argparse
import os
import sys
import yaml

from scripts.deploy import deploy_up, deploy_down, deploy_demo, deploy_status
from scripts.import_adapter import import_run
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
from scripts.restore import backup_restore
from scripts.monitor import monitor_resources


def add_nextcloud_args(parser):
    parser.add_argument(
        "--url",
        default=None,
        help="Nextcloud URL (берётся из NEXTCLOUD_URL / CLI_NEXTCLOUD_URL)"
    )

    parser.add_argument(
        "--username",
        default=None,
        help="Admin username (берётся из NEXTCLOUD_ADMIN_USER)"
    )

    parser.add_argument(
        "--password",
        default=None,
        help="Admin password (берётся из NEXTCLOUD_ADMIN_PASSWORD)"
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


# LOADTEST

def loadtest_run(args):
    # loadtest run --users N
    print("[STUB] Running load test simulation")
    success({
        "simulated_users": args.users,
        "avg_response_ms": 320,
        "errors": 0
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
    # Compose-сервис cli требует REPO_ROOT через ${REPO_ROOT:?...} даже если
    # cli не стартует (он под profile).
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault("REPO_ROOT", repo_root)

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
    restore.add_argument(
        "--components", nargs="+", default=["all"],
        choices=["all", "core", "data"],
        help="Components to restore (default: all available in archive)"
    )
    restore.add_argument(
        "--force", action="store_true",
        help="Skip interactive confirmation (destructive)"
    )
    restore.set_defaults(func=backup_restore)

    # MONITOR
    monitor = subparsers.add_parser("monitor")
    monitor_sub = monitor.add_subparsers(dest="action", required=True)

    resources = monitor_sub.add_parser("resources")
    resources.add_argument(
        "--samples", type=int, default=5,
        help="Number of API latency samples (default: 5)"
    )
    resources.add_argument(
        "--path", default="/status.php",
        help="Endpoint path for response time check (default: /status.php)"
    )
    resources.add_argument(
        "--response-timeout", dest="response_timeout",
        type=float, default=30.0,
        help="HTTP request timeout in seconds (default: 30)"
    )
    resources.add_argument(
        "--interval", type=float, default=0.0,
        help="Seconds between snapshots (0 = one-shot, default: 0)"
    )
    resources.add_argument(
        "--count", type=int, default=1,
        help="Number of snapshots; 0 = unlimited (default: 1)"
    )
    resources.add_argument(
        "--output-dir", dest="output_dir", default=None,
        help="Directory to write per-snapshot JSON files"
    )
    resources.add_argument(
        "--quiet", action="store_true",
        help="Suppress stdout (use with --output-dir)"
    )
    add_nextcloud_args(resources)
    resources.set_defaults(func=monitor_resources)

    # LOADTEST
    loadtest = subparsers.add_parser("loadtest")
    loadtest_sub = loadtest.add_subparsers(dest="action", required=True)

    run = loadtest_sub.add_parser("run")
    run.add_argument("--users", type=int, required=True)
    run.set_defaults(func=loadtest_run)

    # IMPORT - generic CSV -> Nextcloud xlsx upsert
    imp = subparsers.add_parser(
        "import",
        help="Import CSV data into a Nextcloud xlsx (upsert by key)"
    )
    imp.add_argument(
        "--csv", required=True, help="Path to source CSV file"
    )
    imp.add_argument(
        "--target", required=True,
        help="Target xlsx path in Nextcloud "
             "(e.g. /Учебные_таблицы/Группа.xlsx)"
    )
    imp.add_argument(
        "--key", action="append", default=[],
        help="Column name used to match rows. "
             "Repeat the flag for a composite key "
             "(e.g. --key 'repository name' --key number)."
    )
    imp.add_argument(
        "--sheet", default=None,
        help="Target sheet name within xlsx (default: first sheet)"
    )
    imp.add_argument(
        "--separator", default=",",
        help="CSV field separator (default: ','; use ';' for "
             "pandas/Moodle exports)"
    )
    imp.add_argument(
        "--encoding", default="utf-8",
        help="CSV file encoding (default: utf-8)"
    )
    imp.add_argument(
        "--skip-columns", dest="skip_columns", type=int, default=0,
        help="Number of leading CSV columns to drop "
             "(e.g. 1 to skip pandas index column from Moodle exporter)"
    )
    imp.add_argument(
        "--create-if-missing", dest="create_if_missing",
        action="store_true",
        help="Create target xlsx (and parent directories) if it does not "
             "exist; without this flag, missing target is an error"
    )
    add_nextcloud_args(imp)
    imp.set_defaults(func=import_run)

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
        print("Configuration loaded", file=sys.stderr)
    else:
        args.config_data = None

    if args.command is not None:
        args.func(args)


if __name__ == "__main__":
    main()
