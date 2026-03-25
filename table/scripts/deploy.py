import csv
import subprocess
from pathlib import Path

from scripts.nextcloud_client import NextcloudClient
from scripts.upload_xlsx import upload_batch
from scripts.users_from_csv import create_users_from_csv
from scripts.utils import success, error, now


def get_compose_dir(args):
    return (Path(__file__).resolve().parent.parent.parent /
            "playground" /
            "onlyoffice-nextcloud" /
            "deploy").resolve()


def get_compose_file(args):
    return get_compose_dir(args) / "docker-compose.yml"


def get_scripts_dir():
    return Path(__file__).resolve().parent


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
    print("[STUB] docker compose up -d")
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    run_command(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        cwd=compose_dir
    )

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

    run_command(
        ["docker", "compose", "-f", str(compose_file), "down"],
        cwd=compose_dir
    )

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
