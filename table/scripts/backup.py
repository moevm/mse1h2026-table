import datetime
import subprocess
import tarfile
import tempfile
from pathlib import Path

from scripts.deploy import get_compose_dir, get_compose_file
from scripts.utils import error, now, success


def get_backup_dir(args):
    config_dir = None
    if getattr(args, "config_data", None):
        config_dir = args.config_data.get("backup", {}).get("directory")

    if config_dir:
        backup_base = Path(config_dir)
        if not backup_base.is_absolute():
            backup_base = Path(args.project_dir) / config_dir
    else:
        backup_base = Path(args.project_dir) / "backups"

    return backup_base


def backup_create(args):
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    backup_name = (
        args.name
        if getattr(args, "name", None)
        else f"backup-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    backup_base = get_backup_dir(args)
    backup_base.mkdir(parents=True, exist_ok=True)

    backup_archive = backup_base / f"{backup_name}.tar.gz"

    result_files = []

    try:
        temp_dir_obj = tempfile.TemporaryDirectory()
        backup_dir = Path(temp_dir_obj.name)

        components = getattr(args, "components", ["all"])
        if "all" in components:
            components = ["core", "data", "windmill"]

        needs_maintenance = any(c in components for c in ["core", "data"])
        if needs_maintenance:
            cmd_maintenance_on = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "app",
                "php",
                "/var/www/html/occ",
                "maintenance:mode",
                "--on",
            ]
            subprocess.run(cmd_maintenance_on, cwd=compose_dir, check=True)

        if "core" in components:
            db_file = backup_dir / "nextcloud_db_dump.sql"
            cmd_db = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "db",
                "sh",
                "-c",
                'pg_dump -U "$POSTGRES_USER" "${POSTGRES_DB:-nextcloud}"',
            ]
            with open(db_file, "w", encoding="utf-8") as f:
                subprocess.run(cmd_db, cwd=compose_dir, stdout=f, check=True)
            result_files.append(str(db_file))

        if "windmill" in components:
            w_db_file = backup_dir / "windmill_db_dump.sql"
            cmd_w_db = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "windmill-db",
                "sh",
                "-c",
                'pg_dump -U "${WINDMILL_DB_USER:-windmill}" windmill',
            ]
            with open(w_db_file, "w", encoding="utf-8") as f:
                subprocess.run(cmd_w_db, cwd=compose_dir, stdout=f, check=False)
            result_files.append(str(w_db_file))

        if "core" in components:
            core_file = backup_dir / "nextcloud_core.tar.gz"
            cmd_core = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "app",
                "tar",
                "czf",
                "-",
                "-C",
                "/var/www/html",
                "config",
                "themes",
            ]
            with open(core_file, "wb") as f:
                subprocess.run(cmd_core, cwd=compose_dir, stdout=f, check=True)
            result_files.append(str(core_file))

        if "data" in components:
            data_file = backup_dir / "nextcloud_data.tar.gz"
            cmd_data = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "app",
                "tar",
                "czf",
                "-",
                "-C",
                "/var/www/html",
                "data",
            ]
            with open(data_file, "wb") as f:
                subprocess.run(cmd_data, cwd=compose_dir, stdout=f, check=True)
            result_files.append(str(data_file))

        with tarfile.open(backup_archive, "w:gz") as tar:
            tar.add(backup_dir, arcname=backup_name)

    except subprocess.CalledProcessError as e:
        error(f"Ошибка при создании бэкапа: {e}")
    finally:
        if "needs_maintenance" in locals() and needs_maintenance:
            cmd_maintenance_off = [
                "docker",
                "compose",
                "-f",
                str(compose_file),
                "exec",
                "-T",
                "app",
                "php",
                "/var/www/html/occ",
                "maintenance:mode",
                "--off",
            ]
            subprocess.run(cmd_maintenance_off, cwd=compose_dir, check=False)
        try:
            temp_dir_obj.cleanup()
        except Exception:
            pass

    success(
        {
            "backup_id": backup_name,
            "backup_archive": str(backup_archive),
            "status": "created",
            "timestamp": now(),
        },
        args.output,
    )


def backup_list(args):
    backup_base = get_backup_dir(args)
    if not backup_base.exists():
        success({"backups": []}, args.output)

    backups = []
    for file in backup_base.glob("*.tar.gz"):
        stat = file.stat()
        size_mb = stat.st_size / (1024 * 1024)
        name = file.name[:-7] if file.name.endswith(".tar.gz") else file.name
        backups.append(
            {
                "id": name,
                "filename": file.name,
                "size_mb": round(size_mb, 2),
                "created_at": datetime.datetime.fromtimestamp(
                    stat.st_mtime
                ).isoformat(),
            }
        )

    backups.sort(key=lambda x: x["created_at"], reverse=True)

    success(backups, args.output)
