import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from scripts.backup import (
    ENV_HASH_KEYS,
    MANIFEST_NAME,
    _compose_base,
    _env_hashes,
    _maintenance_set,
    _nextcloud_version,
    _occ,
    _parse_env_file,
    _read_manifest_from_archive,
    _try_maintenance_off,
    _warn,
    get_backup_dir,
)
from scripts.deploy import get_compose_dir, get_compose_file
from scripts.utils import error, now, success


def _phase(label):
    """Однострочная отметка прогресса в stderr — чтобы пользователь
    видел, что restore продвигается, не нагружая stdout (там в финале
    лежит JSON/text payload)."""
    print(f"  → {label}", file=sys.stderr)


def _confirm_destructive(prompt):
    """Интерактивное подтверждение. На отказ или Ctrl-D - корректно
    выходим с rc=0 (это не ошибка, а отмена пользователем)."""
    print(prompt, file=sys.stderr)
    try:
        answer = input("Продолжить? [y/N]: ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in ("y", "yes"):
        print("Восстановление отменено.", file=sys.stderr)
        sys.exit(0)


def _check_containers_up(compose_dir, compose_file, services=("app", "db")):
    """Pre-flight для restore: убеждаемся, что нужные контейнеры запущены.
    Иначе docker compose exec упадёт где-то посреди destructive операций."""
    cmd = _compose_base(compose_file) + [
        "ps", "--format", "json", "--all",
    ]
    proc = subprocess.run(
        cmd, cwd=compose_dir, text=True, capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker compose ps упал: "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )

    state_by_service = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        name = item.get("Service") or item.get("service")
        if name:
            state_by_service[name] = (item.get("State") or "").lower()

    missing = [s for s in services if state_by_service.get(s) != "running"]
    if missing:
        raise RuntimeError(
            f"Контейнеры не запущены: {', '.join(missing)}. "
            "Запустите стек: python manage.py deploy up"
        )


def _occ_run_safe(compose_dir, compose_file, label, *occ_args):
    """Выполнить occ с capture; не падать при ошибке, но логировать.
    Используется для пост-restore реконсиляции (files:scan/cleanup,
    maintenance:repair, db:add-missing-indices) - там частичная неудача
    не должна обнулять весь restore."""
    proc = _occ(compose_dir, compose_file, *occ_args, capture=True)
    if proc.returncode != 0:
        out = (proc.stderr or proc.stdout or "").strip()
        _warn(f"{label} (rc={proc.returncode}): {out[:300]}")
        return False
    return True


def _resync_onlyoffice_jwt(compose_dir, compose_file, current_jwt):
    """После restore в БД может лежать старый JWT_SECRET. Контейнер OnlyOffice
    при этом работает с текущим (из .env). Перевыставляем в БД, чтобы
    редактирование документов не сломалось."""
    proc = _occ(
        compose_dir, compose_file,
        "config:app:set", "onlyoffice", "jwt_secret",
        "--value", current_jwt,
        capture=True,
    )
    if proc.returncode != 0:
        out = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"Не удалось перевыставить JWT_SECRET: {out}")


def _patch_config_db_creds(compose_dir, compose_file):
    """Переписать в config.php (внутри контейнера) актуальные значения
    dbname/dbuser/dbpassword/dbhost из текущего deploy/.env. Это нужно
    после восстановления core: бэкап содержит config.php от момента создания,
    а актуальный пароль БД может уже отличаться - иначе occ не подключится."""
    env_path = compose_dir / ".env"
    values = _parse_env_file(env_path)

    config_map = [
        ("dbname", values.get("POSTGRES_DB", "nextcloud")),
        ("dbuser", values.get("POSTGRES_USER", "")),
        ("dbpassword", values.get("POSTGRES_PASSWORD", "")),
        ("dbhost", "db"),
    ]

    for key, value in config_map:
        if not value:
            continue

        # Сначала через occ - наиболее предсказуемый путь.
        proc = _occ(
            compose_dir, compose_file,
            "config:system:set", key, "--value", value,
            capture=True,
        )
        if proc.returncode == 0:
            continue

        # occ не подключается к БД (типичный кейс - старый пароль
        # в восстановленном config.php). Падаем на sed внутри контейнера.
        # Используем '|' как разделитель, чтобы '/'-в-значениях не ломали.
        sed_expr = f"s|'{key}' => '.*'|'{key}' => '{value}'|g"
        sed_cmd = _compose_base(compose_file) + [
            "exec", "-T", "app",
            "sed", "-i", sed_expr,
            "/var/www/html/config/config.php",
        ]
        sed_proc = subprocess.run(
            sed_cmd, cwd=compose_dir, text=True, capture_output=True,
            stdin=subprocess.DEVNULL,
        )
        if sed_proc.returncode != 0:
            err = (sed_proc.stderr or sed_proc.stdout or "").strip()
            raise RuntimeError(
                f"Не удалось обновить {key} в config.php: {err}"
            )


def _pg_terminate_connections(compose_dir, compose_file, service):
    """Best-effort: отстреливаем чужие соединения к текущей БД, чтобы
    DROP SCHEMA не упёрся в зависимости. Не делаем check=True -
    в свежем контейнере pg_stat_activity может быть пустым."""
    sql = (
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = current_database() "
        "AND pid <> pg_backend_pid();"
    )
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "sh", "-c",
        f'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "{sql}"',
    ]
    subprocess.run(
        cmd, cwd=compose_dir, capture_output=True,
        stdin=subprocess.DEVNULL,
    )


def _drop_and_recreate_schema(compose_dir, compose_file, service):
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "sh", "-c",
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c '
        '"DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"',
    ]
    proc = subprocess.run(
        cmd, cwd=compose_dir, text=True, capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"DROP/CREATE SCHEMA упал: {err}")


def _psql_load_dump(compose_dir, compose_file, service, dump_path):
    """Загружаем SQL-дамп через psql. --single-transaction даёт
    «всё или ничего»: при любой ошибке БД откатится в дропнутую схему.
    -q подавляет per-command вывод psql (SET / CREATE TABLE / ...)."""
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "sh", "-c",
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" '
        '--single-transaction -q -v ON_ERROR_STOP=1',
    ]
    with open(dump_path, "rb") as f:
        proc = subprocess.run(
            cmd, cwd=compose_dir, stdin=f,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"psql restore упал (rc={proc.returncode}): {err}"
        )


def _extract_into_container(compose_dir, compose_file, service,
                            target_dir, tar_path, label):
    """Стримим tar-файл с хоста в контейнер и распаковываем там."""
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service,
        "tar", "xf", "-", "-C", target_dir,
    ]
    with open(tar_path, "rb") as f:
        proc = subprocess.run(
            cmd, cwd=compose_dir, stdin=f,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"{label} упал (rc={proc.returncode}): {err}")


def _remove_inside_container(compose_dir, compose_file, service, path):
    """rm -rf внутри контейнера. Параноидальная защита: путь обязан
    начинаться с /var/www/html/ - иначе отказ."""
    if not path.startswith("/var/www/html/"):
        raise RuntimeError(
            f"Отказ удалять путь вне /var/www/html/: {path}"
        )
    cmd = _compose_base(compose_file) + [
        "exec", "-T", service, "rm", "-rf", path,
    ]
    proc = subprocess.run(
        cmd, cwd=compose_dir, text=True, capture_output=True,
        stdin=subprocess.DEVNULL,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"rm -rf {path} упал: {err}")


def _extract_archive(archive_path, target_dir):
    """Распаковка наружного .tar.gz во временную директорию.
    На Python 3.12+ используем filter='data', чтобы tarfile не позволял
    экзотические члены архива (хотя архив мы создаём сами)."""
    extract_kwargs = {}
    if sys.version_info >= (3, 12):
        extract_kwargs["filter"] = "data"
    with tarfile.open(archive_path, "r:gz") as tar:
        tar.extractall(path=target_dir, **extract_kwargs)


def _resolve_restore_components(requested, manifest_components):
    """Какие компоненты реально восстанавливать.
    'all' = всё что лежит в манифесте. Иначе - пересечение с манифестом
    (если запросили то, чего нет в архиве, fail)."""
    archive = list(manifest_components or [])
    requested = list(requested)
    if "all" in requested:
        return archive
    missing = [c for c in requested if c not in archive]
    if missing:
        raise RuntimeError(
            f"Компонент(ы) {missing} отсутствуют в архиве "
            f"(в архиве есть: {sorted(archive)})"
        )
    return [c for c in requested if c in archive]


def _staged_path(staged_dir, manifest, kind, default_name):
    """Найти в распакованном архиве файл нужного 'kind' (по манифесту).
    Имя берём из manifest.files[].name, не хардкодим."""
    for entry in manifest.get("files", []):
        if entry.get("kind") == kind:
            path = staged_dir / entry["name"]
            if path.exists():
                return path
    fallback = staged_dir / default_name
    return fallback if fallback.exists() else None


def _format_pre_restore_summary(manifest, components, env_mismatches,
                                nc_archive, nc_current):
    lines = [
        "",
        f"Архив: {manifest.get('backup_id')} "
        f"(создан {manifest.get('created_at')})",
        f"Будет восстановлено: {components}",
    ]
    if env_mismatches:
        lines.append(
            "  ! ENV-ключи в текущем .env отличаются от бэкапа: "
            f"{', '.join(env_mismatches)}"
        )
        if "JWT_SECRET" in env_mismatches:
            lines.append(
                "    JWT_SECRET будет автоматически перевыставлен в БД "
                "после restore."
            )
        if "POSTGRES_PASSWORD" in env_mismatches:
            lines.append(
                "    POSTGRES_PASSWORD: dbpassword в config.php "
                "будет переписан под текущий .env."
            )
    if nc_archive and nc_current and nc_archive != nc_current:
        lines.append(
            f"  ! Версия Nextcloud отличается: бэкап {nc_archive}, "
            f"текущая {nc_current}. После restore возможно нужен "
            "`occ upgrade`."
        )
    lines.append("")
    lines.append(
        "Восстановление СОТРЁТ текущее состояние выбранных компонентов:"
    )
    if "core" in components:
        lines.append(
            "  - БД Nextcloud: DROP SCHEMA public CASCADE + replay дампа"
        )
        lines.append(
            "  - папки /var/www/html/{config,themes} будут перезаписаны"
        )
    if "data" in components:
        lines.append(
            "  - папка /var/www/html/data будет полностью заменена"
        )
    lines.append("")
    lines.append(
        "Совет: предварительно сохранить текущее состояние:"
    )
    lines.append(
        "  python manage.py backup create --name pre-restore-<метка>"
    )
    return "\n".join(lines)


def backup_restore(args):
    compose_dir = get_compose_dir(args)
    compose_file = get_compose_file(args)

    if not compose_file.exists():
        error(f"Не найден docker-compose.yml: {compose_file}")

    backup_base = get_backup_dir(args)
    backup_id = args.backup_id
    archive_path = backup_base / f"{backup_id}.tar.gz"

    if not archive_path.exists():
        error(f"Архив не найден: {archive_path}")

    manifest = _read_manifest_from_archive(archive_path)
    if manifest is None:
        error(
            f"В архиве {archive_path} нет {MANIFEST_NAME}. "
            "Видимо, бэкап создан несовместимым backup_create. "
            "Восстановление через текущий restore не поддерживается."
        )

    try:
        components = _resolve_restore_components(
            getattr(args, "components", ["all"]),
            manifest.get("components", []),
        )
    except RuntimeError as e:
        error(str(e))

    if not components:
        error("Не выбрано ни одного компонента для восстановления.")

    # Pre-flight: контейнеры запущены.
    try:
        _check_containers_up(compose_dir, compose_file)
    except RuntimeError as e:
        error(str(e))

    # ENV-хеши: сравниваем текущие с теми, что в манифесте.
    current_hashes = _env_hashes(compose_dir)
    archive_hashes = manifest.get("env_hashes", {}) or {}
    env_mismatches = [
        key for key in ENV_HASH_KEYS
        if key in archive_hashes
        and key in current_hashes
        and archive_hashes[key] != current_hashes[key]
    ]

    # Версия NC.
    nc_current = _nextcloud_version(compose_dir, compose_file)
    nc_archive = manifest.get("nextcloud_version")

    # Подтверждение, если не --force.
    if not getattr(args, "force", False):
        summary = _format_pre_restore_summary(
            manifest, components, env_mismatches, nc_archive, nc_current
        )
        _confirm_destructive(summary)

    needs_maintenance = any(c in components for c in ("core", "data"))
    maintenance_on = False
    reconciliation = None
    env_resynced = []

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            _phase("Распаковываю архив")
            _extract_archive(archive_path, tmp_dir)
            staged_dir = tmp_dir / backup_id
            if not staged_dir.is_dir():
                # Если архив создан без префикса <name>/, попробуем плоский.
                staged_dir = tmp_dir

            if needs_maintenance:
                _phase("Включаю maintenance mode")
                _maintenance_set(compose_dir, compose_file, True)
                maintenance_on = True

            # ====== CORE ======
            if "core" in components:
                core_tar = _staged_path(
                    staged_dir, manifest,
                    "filesystem_tar", "nextcloud_core.tar",
                )
                # Берём core-tar явно по paths=['config','themes'].
                core_tar_explicit = None
                for entry in manifest.get("files", []):
                    if entry.get("kind") == "filesystem_tar" and \
                            "config" in (entry.get("paths") or []):
                        core_tar_explicit = staged_dir / entry["name"]
                        break
                core_tar = core_tar_explicit or core_tar

                db_dump = None
                for entry in manifest.get("files", []):
                    if entry.get("kind") == "postgres_dump" and \
                            entry.get("service") == "db":
                        db_dump = staged_dir / entry["name"]
                        break
                if db_dump is None or not db_dump.exists():
                    raise RuntimeError(
                        "В архиве не найден postgres-дамп Nextcloud"
                    )
                if core_tar is None or not core_tar.exists():
                    raise RuntimeError(
                        "В архиве не найден core-tar (config + themes)"
                    )

                _phase("Восстанавливаю core (config + themes + db)")
                # 1. Wipe config/themes.
                _remove_inside_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html/config",
                )
                _remove_inside_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html/themes",
                )

                # 2. Распаковка core-tar.
                _extract_into_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html", core_tar, "tar xf (core)",
                )

                # 3. patch_config: dbcreds -> текущий .env.
                _patch_config_db_creds(compose_dir, compose_file)

                # 4. DB restore.
                _pg_terminate_connections(compose_dir, compose_file, "db")
                _drop_and_recreate_schema(compose_dir, compose_file, "db")
                _psql_load_dump(
                    compose_dir, compose_file, "db", db_dump
                )

                # 5. JWT-resync, если расходится.
                if "JWT_SECRET" in env_mismatches:
                    env_values = _parse_env_file(compose_dir / ".env")
                    current_jwt = env_values.get("JWT_SECRET", "")
                    if current_jwt:
                        _phase("Синхронизирую JWT_SECRET с текущим .env")
                        _resync_onlyoffice_jwt(
                            compose_dir, compose_file, current_jwt
                        )
                        env_resynced.append("JWT_SECRET")

                if "POSTGRES_PASSWORD" in env_mismatches:
                    # Уже учтено в patch_config, просто фиксируем в выводе.
                    env_resynced.append("POSTGRES_PASSWORD")

            # ====== DATA ======
            if "data" in components:
                data_tar = None
                for entry in manifest.get("files", []):
                    if entry.get("kind") == "filesystem_tar" and \
                            "data" in (entry.get("paths") or []):
                        data_tar = staged_dir / entry["name"]
                        break
                if data_tar is None or not data_tar.exists():
                    raise RuntimeError(
                        "В архиве не найден data-tar"
                    )

                _phase("Восстанавливаю файлы пользователей")
                _remove_inside_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html/data",
                )
                _extract_into_container(
                    compose_dir, compose_file, "app",
                    "/var/www/html", data_tar, "tar xf (data)",
                )

            # ====== Реконсиляция при селективном restore ======
            if "core" in components and "data" not in components:
                _phase("Чищу битые ссылки в БД (files:cleanup)")
                _occ_run_safe(
                    compose_dir, compose_file,
                    "files:cleanup", "files:cleanup", "--all",
                )
                reconciliation = "files:cleanup"
            elif "data" in components and "core" not in components:
                _phase("Сканирую новые файлы (files:scan)")
                _occ_run_safe(
                    compose_dir, compose_file,
                    "files:scan", "files:scan", "--all",
                )
                reconciliation = "files:scan"

            # ====== Финальная починка БД/индексов ======
            if "core" in components:
                _phase("maintenance:repair + db:add-missing-indices")
                _occ_run_safe(
                    compose_dir, compose_file,
                    "maintenance:repair", "maintenance:repair",
                )
                _occ_run_safe(
                    compose_dir, compose_file,
                    "db:add-missing-indices", "db:add-missing-indices",
                )

            # Снимаем maintenance.
            if maintenance_on:
                _phase("Выключаю maintenance mode")
                if _try_maintenance_off(compose_dir, compose_file):
                    maintenance_on = False

    except Exception as e:
        if maintenance_on:
            _try_maintenance_off(compose_dir, compose_file)
        error(f"Ошибка при восстановлении: {e}")

    success(
        {
            "backup_id": backup_id,
            "status": "restored",
            "components": components,
            "env_resynced": env_resynced,
            "reconciliation": reconciliation,
            "nextcloud_version": {
                "archive": nc_archive,
                "current": nc_current,
            },
            "manifest_created_at": manifest.get("created_at"),
            "timestamp": now(),
        },
        args.output,
    )
