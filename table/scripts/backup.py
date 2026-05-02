import datetime
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from scripts.deploy import get_compose_dir, get_compose_file
from scripts.utils import error, now, success


MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1

# Грубая прикидка, сколько свободного места нужно сверх размера data.
# 1.3 = ~30% запас под метаданные tar, gzip-неэффективность на бинарниках,
# временный файл до atomic rename.
DISK_SPACE_FUDGE = 1.3
CORE_SIZE_BUDGET = 200 * 1024 * 1024

ENV_HASH_KEYS = (
    "POSTGRES_PASSWORD",
    "JWT_SECRET",
)


def _warn(msg):
    print(f"WARNING: {msg}", file=sys.stderr)


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


def _compose_base(compose_file):
    return ["docker", "compose", "-f", str(compose_file)]


def _occ(compose_dir, compose_file, *occ_args, capture=False):
    cmd = _compose_base(compose_file) + [
        "exec", "-T", "app", "php", "/var/www/html/occ", *occ_args
    ]
    return subprocess.run(
        cmd, cwd=compose_dir, text=True, capture_output=capture
    )


def _maintenance_set(compose_dir, compose_file, on):
    flag = "--on" if on else "--off"
    proc = _occ(
        compose_dir, compose_file, "maintenance:mode", flag, capture=True
    )
    if proc.returncode != 0:
        out = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(
            f"Не удалось переключить maintenance mode ({flag}): {out}"
        )


def _nextcloud_version(compose_dir, compose_file):
    try:
        proc = _occ(
            compose_dir, compose_file,
            "status", "--output=json",
            capture=True,
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)
            return data.get("versionstring") or data.get("version") or None
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _du_in_container(compose_dir, compose_file, service, path):
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "sh", "-c", f"du -sb {path} 2>/dev/null"
    ]
    proc = subprocess.run(
        cmd, cwd=compose_dir, text=True, capture_output=True
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        return int(proc.stdout.split()[0])
    except (ValueError, IndexError):
        return None


def _estimate_needed_bytes(compose_dir, compose_file, components):
    total = 0
    if "core" in components:
        total += CORE_SIZE_BUDGET
    if "data" in components:
        data_size = _du_in_container(
            compose_dir, compose_file, "app", "/var/www/html/data"
        )
        if data_size is None:
            # Если оценить не удалось, не блокируем бэкап - но и не врём,
            # что место точно есть. Берём небольшой fallback.
            data_size = 1 * 1024 * 1024 * 1024  # 1 GiB
        total += data_size
    return int(total * DISK_SPACE_FUDGE)


def _check_disk_space(compose_dir, compose_file, components, target_dir):
    needed = _estimate_needed_bytes(compose_dir, compose_file, components)
    free = shutil.disk_usage(target_dir).free
    if free < needed:
        gb = 1024 ** 3
        raise RuntimeError(
            f"Недостаточно места на диске: нужно ~{needed / gb:.1f} GB, "
            f"доступно {free / gb:.1f} GB в {target_dir}"
        )


def _parse_env_file(env_path):
    values = {}
    if not env_path.exists():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _env_hashes(compose_dir):
    env_path = compose_dir / ".env"
    values = _parse_env_file(env_path)
    hashes = {}
    for key in ENV_HASH_KEYS:
        if key in values and values[key] != "":
            digest = hashlib.sha256(values[key].encode("utf-8")).hexdigest()
            hashes[key] = f"sha256:{digest}"
    return hashes


def _stream_to_file(cmd, cwd, output_path, label):
    """Запустить команду и направить её stdout в файл побайтно."""
    with open(output_path, "wb") as f:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=f, stderr=subprocess.PIPE, check=False
        )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{label} упал (rc={proc.returncode}): {err}")


def _pg_dump(compose_dir, compose_file, service, output_path, label):
    # Внутри обоих postgres-контейнеров пользователь и имя БД лежат
    # в стандартных переменных POSTGRES_USER / POSTGRES_DB
    # (compose маппит наши WINDMILL_DB_* в POSTGRES_*).
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "sh", "-c",
        'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"',
    ]
    _stream_to_file(cmd, compose_dir, output_path, label)


def _tar_inside_container(compose_dir, compose_file, service,
                          base_dir, paths, output_path, label):
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "tar", "cf", "-", "-C", base_dir, *paths
    ]
    _stream_to_file(cmd, compose_dir, output_path, label)


def _build_manifest(compose_dir, compose_file, components, backup_name,
                    files, skipped):
    return {
        "manifest_version": MANIFEST_VERSION,
        "backup_id": backup_name,
        "created_at": datetime.datetime.now().isoformat(),
        "components": list(components),
        "skipped": dict(skipped),
        "nextcloud_version": _nextcloud_version(compose_dir, compose_file),
        "files": files,
        "env_hashes": _env_hashes(compose_dir),
    }


def _try_maintenance_off(compose_dir, compose_file):
    """Безопасное выключение режима обслуживания - не бросает исключение."""
    try:
        _maintenance_set(compose_dir, compose_file, False)
        return True
    except (RuntimeError, OSError) as e:
        _warn(
            f"Не удалось выключить maintenance mode: {e}. "
            f"Выполните вручную: docker compose -f {compose_file} "
            f"exec app php /var/www/html/occ maintenance:mode --off"
        )
        return False


def _resolve_components(requested):
    """Разворачивает 'all' в реальный список компонентов."""
    components = list(requested)
    if "all" in components:
        components = ["core", "data"]
    return components


def backup_create(args):
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    components = _resolve_components(
        getattr(args, "components", ["all"]),
    )
    if not components:
        error("Не выбрано ни одного компонента для бэкапа.")

    backup_name = (
        args.name
        if getattr(args, "name", None)
        else f"backup-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    )

    backup_base = get_backup_dir(args)
    backup_base.mkdir(parents=True, exist_ok=True)

    final_path = backup_base / f"{backup_name}.tar.gz"
    partial_path = backup_base / f"{backup_name}.tar.gz.partial"

    if final_path.exists():
        error(f"Бэкап с таким именем уже существует: {final_path}")
    if partial_path.exists():
        # Остаток от предыдущего падения - безопасно удалить.
        try:
            partial_path.unlink()
        except OSError:
            pass

    # Pre-flight: проверка свободного места ДО включения maintenance.
    try:
        _check_disk_space(
            compose_dir, compose_file, components, backup_base
        )
    except RuntimeError as e:
        error(str(e))

    needs_maintenance = any(c in components for c in ("core", "data"))
    maintenance_on = False
    skipped = {}
    files_meta = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)

            if needs_maintenance:
                _maintenance_set(compose_dir, compose_file, True)
                maintenance_on = True

            members = []  # (host_path, arcname)

            if "core" in components:
                db_file = tmp_dir / "nextcloud_db.sql"
                _pg_dump(
                    compose_dir, compose_file, "db",
                    db_file, "pg_dump (nextcloud)",
                )
                members.append((db_file, "nextcloud_db.sql"))
                files_meta.append({
                    "name": "nextcloud_db.sql",
                    "kind": "postgres_dump",
                    "service": "db",
                    "database": "nextcloud",
                })

                core_file = tmp_dir / "nextcloud_core.tar"
                _tar_inside_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html", ["config", "themes"],
                    core_file, "tar (nextcloud core)",
                )
                members.append((core_file, "nextcloud_core.tar"))
                files_meta.append({
                    "name": "nextcloud_core.tar",
                    "kind": "filesystem_tar",
                    "service": "app",
                    "base": "/var/www/html",
                    "paths": ["config", "themes"],
                })

            if "data" in components:
                data_file = tmp_dir / "nextcloud_data.tar"
                _tar_inside_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html", ["data"],
                    data_file, "tar (nextcloud data)",
                )
                members.append((data_file, "nextcloud_data.tar"))
                files_meta.append({
                    "name": "nextcloud_data.tar",
                    "kind": "filesystem_tar",
                    "service": "app",
                    "base": "/var/www/html",
                    "paths": ["data"],
                })

            # Maintenance можно выключать СЕЙЧАС: внутренние tar/dump
            # уже легли на хост-диск, дальше идёт только локальное сжатие.
            if maintenance_on:
                if _try_maintenance_off(compose_dir, compose_file):
                    maintenance_on = False

            manifest = _build_manifest(
                compose_dir, compose_file,
                components, backup_name, files_meta, skipped,
            )
            manifest_file = tmp_dir / MANIFEST_NAME
            manifest_file.write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            members.insert(0, (manifest_file, MANIFEST_NAME))

            # Атомарная сборка финального артефакта.
            with tarfile.open(partial_path, "w:gz") as tar:
                for src, arcname in members:
                    tar.add(src, arcname=f"{backup_name}/{arcname}")

            os.replace(partial_path, final_path)

    except Exception as e:
        if partial_path.exists():
            try:
                partial_path.unlink()
            except OSError:
                pass
        if maintenance_on:
            _try_maintenance_off(compose_dir, compose_file)
        error(f"Ошибка при создании бэкапа: {e}")

    success(
        {
            "backup_id": backup_name,
            "backup_archive": str(final_path),
            "components": components,
            "skipped": skipped,
            "manifest": manifest,
            "status": "created",
            "timestamp": now(),
        },
        args.output,
    )


def _read_manifest_from_archive(archive_path):
    try:
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(f"/{MANIFEST_NAME}"):
                    f = tar.extractfile(member)
                    if f is None:
                        return None
                    return json.loads(f.read().decode("utf-8"))
    except (tarfile.TarError, json.JSONDecodeError, OSError):
        return None
    return None


def backup_list(args):
    backup_base = get_backup_dir(args)
    if not backup_base.exists():
        success({"backups": []}, args.output)
        return

    backups = []
    for archive in backup_base.glob("*.tar.gz"):
        stat = archive.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        name = archive.name[:-len(".tar.gz")]
        manifest = _read_manifest_from_archive(archive)

        entry = {
            "id": name,
            "filename": archive.name,
            "size_mb": size_mb,
            "created_at": datetime.datetime.fromtimestamp(
                stat.st_mtime
            ).isoformat(),
        }
        if manifest:
            entry["components"] = manifest.get("components")
            entry["skipped"] = manifest.get("skipped") or {}
            entry["nextcloud_version"] = manifest.get("nextcloud_version")
            entry["manifest_created_at"] = manifest.get("created_at")
        else:
            entry["components"] = None
            entry["note"] = "no manifest (legacy archive)"

        backups.append(entry)

    backups.sort(key=lambda x: x["created_at"], reverse=True)
    success({"backups": backups}, args.output)
