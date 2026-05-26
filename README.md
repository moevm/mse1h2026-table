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

## HTTPS

Поддерживаются два варианта терминирования TLS.

### Вариант А - TLS на внешнем reverse proxy

Стек поднимается как есть, HTTPS терминируется внешним reverse proxy перед ним.

Параметры в `deploy/.env`:
- `NEXTCLOUD_HOSTNAME` - публичное DNS-имя, по которому ходит браузер
- `NEXTCLOUD_TRUSTED_PROXIES` - CIDR-подсеть(и) прокси (JSON-массив)

Локальный стенд для проверки с Caddy и self-signed сертификатом - в `playground/caddy-tls-test/`:

```bash
./bin/table-cli deploy up
docker compose -f playground/caddy-tls-test/docker-compose.yml up -d
curl --noproxy '*' -k https://nextcloud.localhost:8443/status.php
```

### Вариант Б - TLS внутри стека

`nginx-server` сам слушает 443 и терминирует TLS.

```bash
# 1. Положить сертификат в deploy/certs/ (server.crt + server.key).
#    Для локальной проверки можно сгенерировать self-signed dev-утилитой:
bash playground/https-test/generate-self-signed.sh nextcloud.localhost

# 2. Поднять стек с HTTPS-overlay
docker compose \
  -f deploy/docker-compose.yml \
  -f deploy/docker-compose.https.yml \
  up -d

# 3. Проверка
curl -k https://nextcloud.localhost:8443/status.php
```

HTTPS-порт меняется через `NEXTCLOUD_HTTPS_PORT` в `deploy/.env` (по умолчанию 8443). HTTP-порт 8080 остаётся открытым и отдаёт `301 → https://`.

Чтобы поставить «настоящий» сертификат (Let's Encrypt, корпоративный CA) - положить `server.crt` (full chain) и `server.key` в `deploy/certs/`, перезапустить `nginx-server`.

Файлы варианта Б:

| Файл | Назначение |
|---|---|
| `deploy/docker-compose.https.yml` | Compose-overlay |
| `deploy/nginx-https.conf` | nginx с 443 + 80→443 redirect. При правках `nginx.conf` синхронизировать здесь |
| `deploy/certs/` | Сертификаты (git-ignored); в проде - реальный `server.crt` + `server.key` |
| `playground/https-test/generate-self-signed.sh` | Dev-утилита: self-signed cert для локального smoke-теста |

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

Чтобы джоба исполнялась без ожидания дефолтного 5-минутного крон-цикла, в стек поднимается отдельный сервис **`cron-worker`** (`deploy/cron-worker.sh`): он каждые `SYNC_INTERVAL` секунд (по умолчанию 10, настраивается в `deploy/.env`) опрашивает `occ background-job:list` и сразу запускает все ожидающие джобы синхронизации форм. Стандартный `cron.php` он тоже зовет - раз в `CRON_INTERVAL` секунд (по умолчанию 300).

Ручной настройки не требуется - `cron-worker` поднимается автоматически вместе с остальным стеком.

**Известное ограничение:** если таблица уже открыта в OnlyOffice **с правами на редактирование** в момент сабмита формы, новая строка не появится в этой сессии сразу - редактор держит локальное состояние из-за конкурентной модели OnlyOffice. Достаточно перезагрузить страницу. Если таблица открывается переходом "Открыть таблицу" из самой формы (после сабмита) - там уже актуальное содержимое.

---

### Поведение системы и выявленные узкие места (Bottlenecks)

Конфигурация стека «из коробки» (с применёнными `php-fpm-pool.conf` правками и `pm.max_children = 30`) на референсном железе **выдерживает 300 одновременных пользователей без 5xx-ошибок**: median latency PROPFIND/OCS 19 мс, деградация заметна только в хвосте (p95 ~1.6 c, p99 ~11 c).

Узкие места при росте нагрузки:
1. **Очередь PHP-FPM:** при >200 одновременных юзерах активные FPM-воркеры доходят до `pm.max_children = 30`, новые запросы становятся в очередь. RAM контейнера `app-server` поднимается с ~550 МБ baseline до пиковых ~1.98 ГБ.
2. **Фоновая нагрузка:** после пиковой активности кратковременно поднимается утилизация `cron-worker` (обрабатывает накопившиеся background-job'ы).
3. **Деградация в хвостах:** время отклика отдельных запросов на пике доходит до 20+ с, при этом median остаётся на уровне 19-30 мс, что типично для FPM с очередью.

### Количественная модель потребления ресурсов

Замеры: `manage.py loadtest run --scenario stepped` параллельно с `manage.py monitor resources --interval 5`, склейка timeline'ов скриптом [`table/loadtest/analyze_resources.py`](table/loadtest/analyze_resources.py). Полный лог и HTML-отчёт лежат в ветке `reports`.

**Стадия с 300 одновременных пользователей (`pm.max_children = 30`):**
| Метрика | Среднее | Пик |
|---|---|---|
| `app-server` CPU | 159 % (~1.6 ядра) | **699 % (~7 ядер)** |
| `app-server` RAM | 629 МБ | **1980 МБ** |
| Все контейнеры CPU | 225 % | 812 % |
| Все контейнеры RAM | 2.2 ГБ | **3.6 ГБ** |
| API latency (`/status.php`) | 162 мс | 3.8 с |

**Производные числа:**
*   **Базовое потребление в простое** — `app-server` ~554 МБ, все контейнеры ~2.1 ГБ.
*   **~48 МБ на воркер PHP-FPM** в пике (delta RAM 1.4 ГБ на 30 воркеров `pm.max_children`). В простое воркеры не аллоцируют — в среднем delta RAM всего ~75 МБ на 300 юзеров.
*   **~43 пользователя на ядро в пике** (300 юзеров / 7 ядер). Это вершина — в среднем дешевле, потому что юзеры в Locust ходят с паузой 1-5 с между запросами.
*   **Throughput**: ~100 req/s aggregate на стадии 300 юзеров (PROPFIND+OCS, 75/25).

### Рекомендуемые требования к инфраструктуре

Исходя из пиковых значений с запасом 1.5×:

| Онлайн пользователи | CPU (vCPU) | RAM (общая) |
| :--- | :--- | :--- |
| **До 50** (базовая) | 2 | 4 ГБ |
| **До 150** | 8 | 8 ГБ |
| **До 300+** | 16 | 16 ГБ |

---

## Заглушки и ограничения

- Адаптер импорта (`manage.py import`) хранит значения как строки - числовые расчеты в формулах будут работать только после ручного «Текст по столбцам» в OnlyOffice.

## Нагрузочное тестирование

`python manage.py loadtest run --scenario stepped` гонит Locust против поднятого стека. Сценарии, флаги, формат результатов — в [`table/loadtest/README.md`](table/loadtest/README.md). Учебные демки Locust против `httpbin` (без Nextcloud) лежат отдельно в [`playground/locust/`](playground/locust/).

Эталонный прогон профиля `stepped` (50→100→200→300 пользователей за 10 минут) — HTML-отчёт, CSV-сводка и серверный timeline лежат в ветке `reports`. Сводные числа клиентской стороны:

| Метрика | Значение |
|---|---|
| Запросов всего | 37 994 |
| Ошибок | 0 |
| Median | 21 мс |
| p90 | 46 мс |
| p95 | 810 мс |
| p99 | 6.4 с |
| Max | 12.9 с |
| Aggregate RPS | ~63 req/s в среднем, ~100 req/s на пике |

---
