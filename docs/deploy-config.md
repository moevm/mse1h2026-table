# Аудит конфигурируемости развёртывания

## Конфигурируемые параметры в deploy/.env

### Администратор Nextcloud

- **NEXTCLOUD_ADMIN_USER** (строка, по умолчанию: `admin`)
  - Имя пользователя администратора Nextcloud при первичной инсталляции
  - **Изменение влияет:** только на первичное создание учётной записи; без пересоздания volumes (сохраняются в БД)

- **NEXTCLOUD_ADMIN_PASSWORD** (строка, по умолчанию: `super_secure_password`)
  - Пароль администратора Nextcloud при первичной инсталляции
  - **Изменение влияет:** только на первичное создание учётной записи; без пересоздания volumes
  - **Важно:** измениться пароль уже существующей инсталляции можно только через Nextcloud web-UI или `occ user:resetpassword`

### Подключение Nextcloud

- **NEXTCLOUD_HOSTNAME** (строка, по умолчанию: `nextcloud.localhost`)
  - Внешний адрес, по которому пользователи обращаются к Nextcloud (FQDN или IP)
  - Используется в trusted_domains и extra_hosts для OnlyOffice
  - **Изменение влияет:** без перезапуска контейнеров (параметр используется только при инициализации и может быть обновлен через `occ config:system:set trusted_domains`)

- **NEXTCLOUD_PORT** (число, по умолчанию: `8080`)
  - Port на хосте для доступа к Nextcloud через nginx
  - **Изменение влияет:** требует перезапуска nginx (`docker compose up -d nginx `)

- **NEXTCLOUD_TRUSTED_PROXIES** (JSON-массив, по умолчанию: `["172.28.0.0/16"]`)
  - CIDR подсеть compose-сети для безопасного доверия заголовкам X-Forwarded-For от nginx
  - **Важно:** должна совпадать с `networks.default.ipam.config.subnet` в docker-compose.yml
  - **Изменение влияет:** без пересоздания volumes (может быть обновлена через `occ config`)

### Криптография и безопасность

- **JWT_SECRET** (строка, по умолчанию: `very_secret_jwt_key`)
  - Секретный ключ для шифрования JWT-токенов в OnlyOffice
  - Используется в nextcloud-init для интеграции OnlyOffice, а также в самом OnlyOffice Document Server
  - **Изменение влияет:** без пересоздания volumes; требует пересоздания контейнеров (`docker compose up --force-recreate app onlyoffice-document-server`)
  - **Важно:** изменение секрета после развёртывания приведёт к разрыву сессий и ошибкам при совместном редактировании

### База данных PostgreSQL

- **POSTGRES_DB** (строка, по умолчанию: `nextcloud`)
  - Имя БД для Nextcloud
  - **Изменение влияет:** только при первичной инициализации БД; **требует пересоздания volume db_data**

- **POSTGRES_USER** (строка, по умолчанию: `nextclouduser`)
  - Пользователь БД
  - **Изменение влияет:** только при первичной инициализации БД; **требует пересоздания volume db_data**

- **POSTGRES_PASSWORD** (строка, по умолчанию: `strongdbpassword`)
  - Пароль пользователя БД
  - **Изменение влияет:** только при первичной инициализации БД; **требует пересоздания volume db_data**
  - **Критично:** параметры БД захардкожены в volumes; изменение без пересоздания volumes приведёт к ошибке подключения

### Локальные параметры

- **TZ** (строка, по умолчанию: `Europe/Moscow`)
  - Временная зона для контейнеров (POSIX TZ format, например `Europe/Moscow`, `UTC`, `Europe/London`)
  - **Изменение влияет:** требует перезапуска контейнеров (`docker compose restart`)

### Планировщик задач (Cron Worker)

- **CRON_INTERVAL** (число в секундах, по умолчанию: `300`)
  - Интервал выполнения стандартного `cron.php` в cron-worker
  - Определяет частоту запуска фоновых задач Nextcloud (индексация файлов, очистка сессий и т.д.)
  - **Изменение влияет:** требует перезапуска cron-worker (`docker compose restart cron-worker`)
  - **Рекомендации:** 
    - Меньшие значения (60-120s) увеличивают нагрузку на БД, но обеспечивают свежесть индексов
    - Значения 300-600s оптимальны для production
    - Значения > 1800s могут привести к задержкам в синхронизации и уведомлениях

- **SYNC_INTERVAL** (число в секундах, по умолчанию: `10`)
  - Интервал синхронизации фоновых задач Forms (обновление связанных файлов)
  - Более частая синхронизация обеспечивает актуальность данных, но увеличивает нагрузку
  - **Изменение влияет:** требует перезапуска cron-worker
  - **Рекомендации:**
    - 5-10s: высокая актуальность, повышенная нагрузка
    - 20-30s: сбалансированный вариант
    - 60s+: минимальная нагрузка, но задержка в обновлениях

## Захардкоженные параметры (осознанно)

### Имена сервисов в compose-сети

Следующие имена сервисов используются внутри контейнеров в кода инициализации и конфигурации. Они захардкожены и соответствуют `container_name` в docker-compose.yml:

- `nginx-server` — прокси для доступа к Nextcloud
- `onlyoffice-document-server` — Document Server для совместного редактирования
- `app` (в compose) / `app-server` — Nextcloud FPM приложение
- `db` (в compose) / `nextcloud-db` — PostgreSQL база данных

**Причина:** эти имена резолвятся через docker network DNS и используются в конфигурационных скриптах (nextcloud-init.sh). Изменение требует обновления инициализационных скриптов.

### Пути в контейнерах

- `/var/www/html` — корневой путь приложения Nextcloud
- `/var/lib/postgresql` — путь БД PostgreSQL
- `/var/www/onlyoffice/Data` — данные OnlyOffice Document Server

**Причина:** эти пути стандартны для используемых базовых образов и не требуют изменения.

### Версии образов

- `nextcloud:33.0-fpm` — зафиксирована на конкретной версии для стабильности
- `postgres:18` — PostgreSQL 18
- `onlyoffice/documentserver:9.3` — OnlyOffice Document Server
- `nginx:stable-alpine` — nginx стабильной версии

**Причина:** обновление версий требует тестирования совместимости и может привести к миграции данных.

## Файлы конфигурации и инициализации

### deploy/.env

Главный файл конфигурации. Переменные из этого файла подставляются в docker-compose.yml и передаются в контейнеры как переменные окружения.

### deploy/docker-compose.yml

Оркестрация контейнеров. Содержит:
- Определение сервисов (app, db, nginx, onlyoffice-document-server, cron-worker, nextcloud-init, cli)
- Подключение volume'ов для persistence
- Конфигурацию сети и trusted_proxies
- Resource limits для каждого сервиса

### deploy/nextcloud-init.sh

Скрипт инициализации Nextcloud при первом старте:
- Ожидание полной инсталляции приложения
- Установка и конфигурация приложений (OnlyOffice, Forms)
- Настройка trusted_domains, trusted_proxies и других параметров безопасности
- Запуск обслуживания БД и indices

### deploy/cron-worker.sh

Фоновый рабочий, выполняющий:
- Синхронизацию фоновых задач Forms (SyncSubmissionsWithLinkedFileJob)
- Выполнение стандартного cron.php для обслуживания приложения
- Корректное обращение SIGTERM при остановке контейнера

### deploy/cron-worker.Dockerfile

Dockerfile для построения образа cron-worker на основе nextcloud:33.0-fpm с установкой `jq` для парсинга JSON.

### deploy/php-fpm-pool.conf

Конфигурация FPM worker pool'а для оптимизации обработки запросов.

### deploy/php-fpm-logging.conf

Конфигурация логирования FPM.

### deploy/nginx.conf

Конфигурация nginx с поддержкой:
- Reverse proxy к Nextcloud FPM
- Проксирования запросов к OnlyOffice Document Server на `/ds-vpath/`
- Health checks

## Resource Limits

Все контейнеры имеют жёстко сконфигурированные ограничения по ресурсам. В текущей конфигурации также используется параметр `cpuset`, который принудительно привязывает выполнение всех контейнеров к нулевому и первому ядрам процессора.

| Сервис | CPU Limit (`cpus`) | CPU Set (`cpuset`) | Memory Limit (`mem_limit`) | Memory Reservation (`mem_reservation`) |
|--------|-------------------|--------------------|---------------------------|---------------------------------------|
| app (Nextcloud) | 2.0 | 0-1 | 2G | 1G |
| db (PostgreSQL) | 1.0 | 0-1 | 1536M | 512M |
| onlyoffice-document-server | 2.0 | 0-1 | 2G | 1G |
| nginx | 0.5 | 0-1 | 256M | 128M |
| nextcloud-init | 1.0 | 0-1 | 512M | 256M |
| cron-worker | 1.0 | 0-1 | 512M | 256M |
| cli (tools) | 1.0 | 0-1 | 512M | 256M |

**Примечание:** эти значения могут быть отрегулированы в зависимости от ожидаемой нагрузки (количества активных пользователей) и доступных ресурсов хост-машины.

## Сеть

Compose проект использует пользовательскую bridge-сеть с фиксированной подсетью `172.28.0.0/16`. Это необходимо для:
- Согласованного matching NEXTCLOUD_TRUSTED_PROXIES с реальной подсетью контейнеров
- Предотвращения конфликтов с другими compose-проектами на машине
- Корректной маршрутизации трафика между контейнерами

Если подсеть уже занята другим проектом, измените оба значения:
1. `networks.default.ipam.config.subnet` в docker-compose.yml
2. `NEXTCLOUD_TRUSTED_PROXIES` в .env

## Volumes

Все основные данные хранятся в named volumes для persistence:

- **app_data**: Nextcloud приложение и пользовательские файлы (`/var/www/html`)
- **db_data**: PostgreSQL данные (`/var/lib/postgresql`)
- **document_data**: OnlyOffice Document Server данные (`/var/www/onlyoffice/Data`)
- **document_log**: OnlyOffice логи (`/var/log/onlyoffice`)

**Важно:** удаление volumes приведёт к потере всех данных. Для полного сброса:

```bash
docker compose down -v  # -v удаляет все volumes
```

## Операции развёртывания


### Обновление параметров

**Параметры без перезапуска контейнеров:**
- NEXTCLOUD_HOSTNAME (используется только при инициализации)
- NEXTCLOUD_TRUSTED_PROXIES (при наличии пересоздания app и повторного запуска nextcloud-init)

**Параметры с перезапуском контейнеров:**
- TZ (все контейнеры)
- NEXTCLOUD_PORT (nginx)
- JWT_SECRET (app, onlyoffice-document-server, требуется пересоздание: `docker compose up --force-recreate app onlyoffice-document-server`)
- CRON_INTERVAL, SYNC_INTERVAL (cron-worker)

**Параметры, требующие пересоздания volumes:**
- POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD (требует `docker compose down -v && docker compose up -d`)

