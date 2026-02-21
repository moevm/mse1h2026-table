import argparse
import sys
import json
import datetime


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


# =========================
# DEPLOY
# =========================

def deploy_up(args):
    # deploy up
    print("[STUB] docker compose up -d")
    success({
        "services": ["nextcloud", "onlyoffice", "postgres", "redis"],
        "status": "running",
        "timestamp": now()
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
        "nextcloud": "running",
        "onlyoffice": "running",
        "postgres": "running",
        "redis": "running"
    }, args.output)


# =========================
# USERS
# =========================

def users_create(args):
    # users create [user]
    print(f"[STUB] Creating Nextcloud user: {args.user}")
    success({
        "username": args.user,
        "status": "created",
        "timestamp": now()
    }, args.output)


def users_delete(args):
    # users delete [user]
    print(f"[STUB] Deleting Nextcloud user: {args.user}")
    success({
        "username": args.user,
        "status": "deleted"
    }, args.output)


def users_list(args):
    # users list
    success({
        "users": [
            {"username": "admin"},
            {"username": "student1"},
            {"username": "student2"}
        ]
    }, args.output)


# =========================
# BACKUP
# =========================

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


# =========================
# MIGRATE
# =========================

def migrate_status(args):
    # migrate status
    success({
        "current_version": "28.0.2",
        "available_version": "28.1.0",
        "upgrade_required": True
    }, args.output)


def migrate_apply(args):
    # migrate apply
    print("[STUB] Creating automatic backup before migration")
    print("[STUB] Running occ upgrade")
    print("[STUB] Restarting services")

    success({
        "migration": "completed",
        "backup_created": True,
        "timestamp": now()
    }, args.output)


# =========================
# MONITOR
# =========================

def monitor_status(args):
    # monitor status
    success({
        "overall": "OK",
        "nextcloud": {"status": "ok", "response_ms": 210},
        "onlyoffice": {"status": "ok", "response_ms": 150}
    }, args.output)


def monitor_resources(args):
    # monitor resources
    success({
        "cpu_percent": 32,
        "memory_mb": 1024,
        "disk_free_gb": 120
    }, args.output)


def monitor_load_test(args):
    # monitor load-test [users]
    print("[STUB] Running load test simulation")
    success({
        "simulated_users": args.users,
        "avg_response_ms": 320,
        "errors": 0
    }, args.output)


# INTEGRATIONS

def integrations_run(args):
    # integrations [module]
    print(f"[STUB] Running integration module: {args.module}")
    success({
        "module": args.module,
        "status": "completed",
        "rows_exported": 120
    }, args.output)


# CLI Definition

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", choices=["text", "json"], default="text")

    subparsers = parser.add_subparsers(dest="command")

    # DEPLOY
    deploy = subparsers.add_parser("deploy")
    deploy_sub = deploy.add_subparsers(dest="action")

    deploy_sub.add_parser("up").set_defaults(func=deploy_up)
    deploy_sub.add_parser("down").set_defaults(func=deploy_down)
    deploy_sub.add_parser("status").set_defaults(func=deploy_status)

    # USERS
    users = subparsers.add_parser("users")
    users_sub = users.add_subparsers(dest="action")

    create = users_sub.add_parser("create")
    create.add_argument("user")
    create.set_defaults(func=users_create)

    delete = users_sub.add_parser("delete")
    delete.add_argument("user")
    delete.set_defaults(func=users_delete)

    users_sub.add_parser("list").set_defaults(func=users_list)

    # BACKUP
    backup = subparsers.add_parser("backup")
    backup_sub = backup.add_subparsers(dest="action")

    backup_sub.add_parser("create").set_defaults(func=backup_create)
    backup_sub.add_parser("list").set_defaults(func=backup_list)

    restore = backup_sub.add_parser("restore")
    restore.add_argument("backup_id")
    restore.set_defaults(func=backup_restore)

    # MIGRATE
    migrate = subparsers.add_parser("migrate")
    migrate_sub = migrate.add_subparsers(dest="action")

    migrate_sub.add_parser("status").set_defaults(func=migrate_status)
    migrate_sub.add_parser("apply").set_defaults(func=migrate_apply)

    # MONITOR
    monitor = subparsers.add_parser("monitor")
    monitor_sub = monitor.add_subparsers(dest="action")

    monitor_sub.add_parser("status").set_defaults(func=monitor_status)
    monitor_sub.add_parser("resources").set_defaults(func=monitor_resources)

    load_test = monitor_sub.add_parser("load-test")
    load_test.add_argument("users", type=int)
    load_test.set_defaults(func=monitor_load_test)

    # INTEGRATIONS
    integrations = subparsers.add_parser("integrations")
    integrations.add_argument("module")
    integrations.set_defaults(func=integrations_run)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()