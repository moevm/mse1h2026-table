# mse1h2026-table

Self-hosted онлайн таблицы для кафедры на базе **Nextcloud + OnlyOffice**.
Стек поднимается одной командой через Docker Compose, эксплуатация (пользователи,
загрузка таблиц, бэкапы, мониторинг, импорт из внешних CSV) - через CLI
`manage.py` / `bin/table-cli`.

---

## Требования

- [Docker](https://docs.docker.com/get-started/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/)
- Git
- Python 3.x - **только** если запускаете CLI напрямую через `python3 manage.py`. Если идете через `./bin/table-cli` (см. ниже), Python на хосте не требуется.

---

## Поддерживаемые ОС

- **Linux / macOS** - основной режим, все работает напрямую.
- **Windows** - рекомендуется [WSL2](https://learn.microsoft.com/windows/wsl/install) с Docker Desktop. При работе из WSL действия аналогичны Linux. Без WSL - нужен Docker Desktop, hosts-файл лежит по `C:\Windows\System32\drivers\etc\hosts`

## Подготовка хоста

В hosts-файл добавить запись (один раз):

```
127.0.0.1   nextcloud.localhost
```

На Linux / macOS / WSL:

```bash
echo "127.0.0.1   nextcloud.localhost" | sudo tee -a /etc/hosts
```

На Windows (PowerShell от администратора):

```powershell
Add-Content -Path "$env:windir\System32\drivers\etc\hosts" -Value "`n127.0.0.1`tnextcloud.localhost"
```

Дефолтный URL стека после старта для локального запуска - **http://nextcloud.localhost:8080**. Порт меняется через `NEXTCLOUD_PORT` в `deploy/.env`, hostname - через `NEXTCLOUD_HOSTNAME` (с синхронной правкой hosts-файла).

## Авторизация в Nextcloud

После `deploy up` веб-интерфейс открывается по http://nextcloud.localhost:8080 со следующими дефолтными admin-кредами:

- **Логин:** `admin`
- **Пароль:** `super_secure_password`

Эти значения лежат в `deploy/.env` под именами `NEXTCLOUD_ADMIN_USER` и `NEXTCLOUD_ADMIN_PASSWORD`. Перед production-развертыванием - поменять и пересоздать стек (`deploy down` -> удалить volume `app_data` -> `deploy up`), иначе старый пароль в БД переживет правку `.env`.

---

## Запуск CLI: два равнозначных варианта

### A. Контейнеризованный CLI

Из корня репозитория:

```bash
./bin/table-cli <subcommand> [args...]
```

Wrapper собирает образ `mse1h2026-table-cli` при первом вызове и проксирует аргументы в `manage.py` внутри контейнера. На хосте нужен только Docker.

Все примеры ниже с `python3 manage.py …` имеют точный эквивалент `./bin/table-cli …` с теми же флагами:

```bash
./bin/table-cli deploy up
./bin/table-cli deploy demo
./bin/table-cli users list --details
./bin/table-cli backup create --components data --name nightly
```

**Как это работает.** Контейнер cli монтирует `/var/run/docker.sock` - это нужно, чтобы `backup` / `restore` / `monitor` / `deploy *` могли управлять остальными сервисами стека (`docker compose exec` для `occ`, `pg_dump`, `docker stats` и т.д.). Локальные файлы (CSV, xlsx, backup-архивы) передавайте путями относительно корня репо или абсолютными - wrapper монтирует репо по тому же пути, что на хосте.

### B. Host-Python (dev-режим)

```bash
cd table
python3 -m venv .venv && source .venv/bin/activate    # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
python3 manage.py <subcommand> [args...]
```

Виртуальное окружение опционально, но без него `pip install` будет ругаться на externally-managed-environment в Debian 12+ / Ubuntu 24.04+ / Homebrew.

Все команды `manage.py` запускаются именно из `mse1h2026-table/table/` - иначе сломаются относительные импорты `scripts.*`.

---

## Команды

### `deploy` - управление стеком

```bash
# Поднять весь стек 
python3 manage.py deploy up

# Остановить
python3 manage.py deploy down

# Дождаться полной готовности (containers + DB + Nextcloud /status.php + nginx)
python3 manage.py deploy status --wait --timeout 1200 --interval 10

# Наполнить демо-данными: пользователи из scripts/users_example.csv,
# .xlsx из scripts/*.xlsx уходят в /Учебные_таблицы, шарятся группам
python3 manage.py deploy demo
```

`deploy status` без `--wait` возвращает текущий снимок состояния - удобно для health-check скриптов / мониторинга.

## HTTPS за внешним прокси

TLS терминируется на внешнем reverse proxy, а сам compose-стек остаётся на HTTP.

Что нужно задать в `deploy/.env`:
- `NEXTCLOUD_HOSTNAME` - публичное DNS-имя
- `NEXTCLOUD_TRUSTED_PROXIES` - IP или подсеть прокси

Для локальной проверки HTTPS есть отдельный стенд `playground/caddy-tls-test/` с Caddy и self-signed сертификатом. Запуск:
```bash
./bin/table-cli deploy up
docker compose -f playground/caddy-tls-test/docker-compose.yml up -d
curl --noproxy '*' -k https://nextcloud.localhost:8443/status.php
```

### `users` - управление пользователями Nextcloud

```bash
# Просмотр
python3 manage.py users list                                 # только логины
python3 manage.py users list --details                       # email, группы, квота

# Фильтр: поле <username|email|group> + режим <contains|prefix|exact> + значение
python3 manage.py users list --filter username prefix adm
python3 manage.py users list --filter email contains example.com --details
python3 manage.py users list --filter group exact admin --details
# Несколько фильтров - комбинируются по AND
python3 manage.py users list --filter username prefix adm --filter email contains mail.ru --details

# Создание / удаление одиночных пользователей
python3 manage.py users create <login> --email <e> --display-name <n> \
    --user-password <p> --quota 1GB --groups <g1> <g2>
python3 manage.py users delete <login>

# Массовые операции из CSV (создает недостающие группы автоматически)
python3 manage.py users csv-create <path/to/users.csv>
python3 manage.py users csv-delete <path/to/users.csv>
```

CSV должен содержать как минимум колонки `login` и `password`; опционально `email`, `display_name`, `quota`, `groups` (через запятую), `subadmin_groups`. Образец - `table/scripts/users_example.csv`.

### `upload` - загрузка .xlsx таблиц в Nextcloud

```bash
# Один файл
python3 manage.py upload --file <path/to/file.xlsx> --dest /папка --name "Название"

# Все .xlsx из директории
python3 manage.py upload --dir <path/to/dir> --dest /папка
```

Папки назначения создаются автоматически

### `import` - CSV -> xlsx (upsert по ключу)

Адаптер для подкачки данных из произвольных CSV (выгрузка GitLogger, LMS-экспортера и др.) в существующую xlsx-таблицу в Nextcloud. Логика **upsert по ключевым колонкам**: строки с совпадающим ключом обновляются, новые добавляются в конец, нетронутые остаются как есть. Если в CSV появились новые колонки - они дописываются в header.

```bash
# GitLogger commits
python3 manage.py import \
  --csv ./out.csv \
  --target /Учебные_таблицы/Группа5300_коммиты.xlsx \
  --key "commit id"

# Композитный ключ (issues по нескольким репо)
python3 manage.py import \
  --csv ./issues.csv \
  --target /Учебные_таблицы/Issues.xlsx \
  --key "repository name" --key number

# Moodle-экспорт: разделитель `;` + пропустить pandas-индексную колонку
python3 manage.py import \
  --csv ./moodle_course_12345.csv \
  --target /Учебные_таблицы/Курс12345_оценки.xlsx \
  --key username \
  --separator ";" \
  --skip-columns 1

# Создать target вместе с импортом
python3 manage.py import --csv ./out.csv \
  --target /Учебные_таблицы/Новая_папка/новая_таблица.xlsx \
  --key "commit id" \
  --create-if-missing
```

Все флаги:

| Флаг | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--csv PATH` | да | - | путь к локальному CSV-файлу |
| `--target PATH` | да | - | путь к xlsx внутри Nextcloud (`/Учебные_таблицы/Группа.xlsx`) |
| `--key COL` | да | - | имя колонки-ключа; повторите флаг для составного ключа |
| `--sheet NAME` | нет | первый лист | имя листа внутри xlsx |
| `--separator C` | нет | `,` | разделитель полей (`;` для pandas/Moodle) |
| `--encoding ENC` | нет | `utf-8` | кодировка CSV |
| `--skip-columns N` | нет | `0` | сколько ведущих колонок CSV отбросить (pandas-index) |
| `--create-if-missing` | нет | выкл. | создать пустой xlsx (и недостающие папки), если target не существует |

**Ограничения:**
- В момент импорта файл не должен быть открыт в OnlyOffice - иначе можно получить либо HTTP ошибку 423 (locked), либо параллельные правки в редакторе будут перезаписаны при PUT.
- Адаптер не парсит числа/даты - значения хранятся как строки, OnlyOffice сам определит формат при отображении.

### `backup` - резервное копирование и восстановление

```bash
# Создать бэкап (по умолчанию --components all = core + data)
python3 manage.py backup create
python3 manage.py backup create --components data --name nightly
python3 manage.py backup create --components core --name pre-upgrade

# Список бэкапов с метаданными
python3 manage.py backup list

# Восстановление (--force пропускает интерактивное подтверждение)
python3 manage.py backup restore <backup_id>
python3 manage.py backup restore <backup_id> --components data --force
```

Где лежат архивы:
- по умолчанию `<repo>/table/backups/<backup_id>.tar.gz`;
- при `--config <yaml>` путь берется из ключа `backup.directory`.

`core` = БД Nextcloud (pg_dump) + `/var/www/html/{config,themes}`.  
`data` = `/var/www/html/data` (файлы пользователей).

Restore выключает maintenance mode перед `files:scan` / `files:cleanup` / `maintenance:repair` / `db:add-missing-indices` - иначе реконсилиация не отрабатывает и в индексе Некстклауда остаются призрачные файлы.

При несовпадении `JWT_SECRET` / `POSTGRES_PASSWORD` между `.env` бэкапа и текущим - restore автоматически перевыставляет соответствующие значения в БД и `config.php` через `occ`. Список перевыставленных ключей попадает в `env_resynced` итогового JSON.

### `monitor resources` - метрики стека

Снимает CPU/RAM по контейнерам, время отклика API, число активных пользовательских сессий Nextcloud и свободное место.

```bash
# Разовый замер
python3 manage.py monitor resources

# JSON-формат (для парсинга)
python3 manage.py --output json monitor resources

# Замерить latency на /index.php/login вместо /status.php
python3 manage.py monitor resources --path /index.php/login

# Периодический сбор (12 снимков с интервалом 5 секунд)
python3 manage.py --output json monitor resources --interval 5 --count 12

# Бесконечный сбор (Ctrl-C для остановки)
python3 manage.py --output json monitor resources --interval 5 --count 0

# Каждый снимок - в отдельный JSON-файл
python3 manage.py monitor resources --interval 5 --count 12 --output-dir ./metrics

# Тихий режим (без stdout, только в файлы)
python3 manage.py monitor resources --interval 5 --count 0 --output-dir ./metrics --quiet
```

| Флаг | По умолчанию | Описание |
|---|---|---|
| `--samples N` | 5 | сколько HTTP-запросов делать для усреднения времени отклика |
| `--path PATH` | `/status.php` | endpoint для замера latency |
| `--response-timeout S` | 30 | таймаут одного HTTP-запроса в секундах |
| `--interval N` | 0 | секунд между снепшотами (0 = одноразовый замер) |
| `--count M` | 1 | сколько снепшотов сделать (0 = бесконечно) |
| `--output-dir DIR` | - | каждый снепшот пишется в `DIR/metrics_<timestamp>.json` |
| `--quiet` | false | подавить вывод в stdout (используется с `--output-dir`) |

**Важно:** глобальный флаг `--output text|json` пишется **до** subcommand'а: `python3 manage.py --output json monitor resources ...`.

---

## Формы -> таблицы

Связка форм и таблиц осуществляется **полностью внутри Nextcloud**: в форме во вкладке "Результаты" доступно действие "Создать электронную таблицу", и Nextcloud Forms регистрирует фоновую джобу `OCA\Forms\BackgroundJob\SyncSubmissionsWithLinkedFileJob`, которая на каждый новый ответ дописывает строку в xlsx.

Чтобы джоба исполнялась без ожидания дефолтного 5-минутного крон-цикла, в стек поднимается отдельный сервис **`cron-worker`** (`deploy/cron-worker.sh`): он каждые 10 секунд опрашивает `occ background-job:list` и сразу запускает все ожидающие джобы синхронизации форм. Стандартный `cron.php` он тоже зовет - раз в 5 минут.

Ручной настройки не требуется - `cron-worker` поднимается автоматически вместе с остальным стеком.

---

### Поведение системы и выявленные узкие места (Bottlenecks)
Конфигурация стека «из коробки» (ограниченная параметром `pm.max_children = 30` в `php-fpm-pool.conf`) стабильно выдерживает **до 50 активных пользователей** со средним временем отклика API в 20-30 мс.

При превышении порога в 100-300 пользователей:
1. **Исчерпание пула PHP-FPM:** Потребление RAM контейнером `app-server` упирается в «потолок» ~1.1 ГБ. Новые запросы ставятся в очередь, время отклика деградирует с 20 мс до **5–16 секунд**.
2. **Нехватка CPU:** Утилизация процессора контейнером `app-server` вырастает до **400-488%** (требуется почти 5 полных ядер).
3. **Таймауты:** Nginx начинает сбрасывать соединения, процент отказов (ошибки `503` и `504`) достигает ~15%.
4. **Фоновая нагрузка:** После пиковой активности резко возрастает утилизация контейнера `cron-worker` (до 80-100% CPU) для обработки накопившихся очередей задач.

### Количественная модель потребления ресурсов
Выведены следующие зависимости:
*   **1 пользователь PHP-FPM** потребляет в среднем **~20-25 МБ RAM**.
*   **1 ядро процессора (vCPU)** способно эффективно обрабатывать запросы от **~40-50 одновременно активных пользователей**.
*   Базовое потребление системы (Nextcloud, OnlyOffice, DB в простое) составляет ~1.6 ГБ RAM.

### Рекомендуемые требования к инфраструктуре

| Онлайн пользователи | Необходимый CPU | Необходимая RAM (общая) |
| :--- | :--- | :--- |
| **До 50** (базовая) | 2 vCPU | 4 ГБ |
| **До 150** | 8 vCPU | 8 ГБ |
| **До 300+** | 16 vCPU | 16 ГБ |

---

## Заглушки и ограничения

- `manage.py loadtest run` - заглушка, возвращает фиктивные числа. Полноценное нагрузочное тестирование пока не реализовано.
- Адаптер импорта (`manage.py import`) хранит значения как строки - числовые расчеты в формулах будут работать только после ручного -Текст по столбцам" в OnlyOffice.

---
