from scripts.users_from_csv import create_users_from_csv, delete_users_from_csv
from scripts.utils import success, error, now
from scripts.nextcloud_client import NextcloudClient


# USERS

def users_create(args):
    # users create [user]

    client = NextcloudClient(args.url, args.username, args.password)

    try:
        client.create_user(
            userid=args.user,
            email=args.email,
            displayName=args.display_name,
            password=args.user_password,
            quota=args.quota,
            groups=args.groups
        )
        success({
            "username": args.user,
            "status": "created",
            "timestamp": now()
        }, args.output)

    except Exception as e:
        error(f"Failed to create user '{args.user}': {e}")


def users_delete(args):
    # users delete [user]

    client = NextcloudClient(args.url, args.username, args.password)

    try:
        client.delete_user(args.user)
        success({
            "username": args.user,
            "status": "deleted",
            "timestamp": now()
        }, args.output)

    except Exception as e:
        error(f"Failed to delete user '{args.user}': {e}")


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
    client = NextcloudClient(args.url, args.username, args.password)

    try:
        users = client.get_users()

        if getattr(args, "prefix", None):
            users = [u for u in users if u.startswith(args.prefix)]

        need_details = getattr(args, "details", False)
        if args.filter:
            need_details = need_details or any(
                field != "username" for field, _, _ in args.filter
            )

        result = []
        for u in users:
            details = None
            if need_details:
                details = client.get_user_details(u)

            passed = True
            if args.filter:
                for field, mode, value in args.filter:
                    v = None

                    if field == "username":
                        v = u
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
                result.append(details)
            else:
                result.append(u)

        success({"users": result}, args.output)

    except Exception as e:
        error(f"Failed to fetch users: {e}")
