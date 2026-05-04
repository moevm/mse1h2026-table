# mse1h2026-table

## Требования

Перед началом убедитесь, что установлены:

- [Docker](https://docs.docker.com/get-started/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/)
- Python 3.x
- Git

---

## Необходимые настройки

Добавьте запись в файл `/etc/hosts` (требуется один раз):
```
127.0.0.1   nextcloud.localhost
```

На Linux/macOS это можно сделать командой:
```bash
echo "127.0.0.1   nextcloud.localhost" | sudo tee -a /etc/hosts
```

---
## Установка и запуск

1. Склонируйте репозиторий и перейдите в него:
 
```bash
git clone https://github.com/moevm/mse1h2026-table.git
cd mse1h2026-table
```
 
2. Перейдите в папку `table/` — все дальнейшие команды `manage.py` выполняются отсюда:
 
```bash
cd table
```

3. Запустить систему:
```bash
   python manage.py deploy up
```
   Или напрямую через Docker Compose (из папки `deploy/`):
```bash
   cd deploy
   docker compose up -d
```

4. После запуска Nextcloud (с подключённым OnlyOffice) доступен по адресу:
   **http://nextcloud.localhost:8080**

   При необходимости порт можно изменить через переменную `NEXTCLOUD_PORT` в файле `deploy/.env`.

5. Дождаться полной готовности системы:
```bash
python manage.py deploy status --wait
```

6. Наполнить систему тестовыми данными:
```bash
   python manage.py deploy demo
```

7. Для остановки:
```bash
python manage.py deploy down
```

Или напрямую через Docker Compose (из папки `deploy/`):
```bash
cd deploy
docker compose down
```
---

## Работа с пользователями Nextcloud через manage.py
Все команды выполняются из папки `table/`:
```bash
cd table
```

### Просмотр пользователей

- Показать всех пользователей (только логины):
  ```bash
  python manage.py users list
  ```

- Показать всех пользователей с подробностями (email, группы, квота):
  ```
  python manage.py users list --details
  ```

#### Фильтрация пользователей

Для гибкой фильтрации используйте флаг --filter <поле> <режим> <значение>. Можно указывать несколько фильтров подряд.

- По username (начинается с 'adm'):
  ```
  python manage.py users list --filter username prefix adm
  ```
- По email (содержит 'example.com'):
  ```
  python manage.py users list --filter email contains example.com --details
  ```
- По группе (точное совпадение 'admin'):
  ```
  python manage.py users list --filter group exact admin --details
  ```
- Комбинированные фильтры:
  ```
  python manage.py users list --filter username prefix adm --filter email contains mail.ru --details
  ```

#### Описание фильтров
- <поле>: username, email, group
- <режим>: contains (содержит), prefix (начинается с), exact (точное совпадение)
- <значение>: строка для поиска

- Для просмотра email, групп и квоты используйте флаг --details.
- Флаг --prefix также работает для фильтрации по началу username.

### Создание и удаление пользователей

- Создать одного пользователя:
```bash
  python manage.py users create <username> --email <email> --display-name <name> --user-password <password> --quota 1GB --groups <group>
```
- Удалить одного пользователя:
```bash
  python manage.py users delete <username>
```
- Создать пользователей из CSV:
```bash
  python manage.py users csv-create <path/to/file.csv>
```
- Удалить пользователей из CSV:
```bash
  python manage.py users csv-delete <path/to/file.csv>
```

### Загрузка таблиц

- Загрузить один файл:
```bash
  python manage.py upload --file <path/to/file.xlsx> --dest /папка --name "Название"
```
- Загрузить все файлы из директории:
```bash
  python manage.py upload --dir <path/to/dir> --dest /папка
```

#### Мониторинг ресурсов

Сбор метрик нагрузки: CPU/RAM по контейнерам, время отклика API, число активных пользовательских сессий Nextcloud, свободное место.

Разовый замер:
```bash
python manage.py monitor resources
```

В формате JSON:
```bash
python manage.py --output json monitor resources
```

Указать другой endpoint для замера времени отклика (по умолчанию `/status.php`):
```bash
python manage.py monitor resources --path /index.php/login
```

Периодический сбор (например каждые 5 секунд, 12 раз):
```bash
python manage.py --output json monitor resources --interval 5 --count 12
```

Бесконечный сбор (Ctrl-C для остановки):
```bash
python manage.py --output json monitor resources --interval 5 --count 0
```

Сохранять каждый снепшот в отдельный JSON-файл:
```bash
python manage.py monitor resources --interval 5 --count 12 --output-dir ./metrics
```

Тихий режим (без вывода в консоль, только в файлы):
```bash
python manage.py monitor resources --interval 5 --count 0 --output-dir ./metrics --quiet
```

Все флаги:

| Флаг | По умолчанию | Описание |
|---|---|---|
| `--samples N` | 5 | сколько HTTP-запросов делать для усреднения времени отклика |
| `--path PATH` | `/status.php` | endpoint для замера latency |
| `--response-timeout S` | 30 | таймаут одного HTTP-запроса в секундах |
| `--interval N` | 0 | секунд между снепшотами (0 = одноразовый замер) |
| `--count M` | 1 | сколько снепшотов сделать (0 = бесконечно) |
| `--output-dir DIR` | — | каждый снепшот пишется в `DIR/metrics_<timestamp>.json` |
| `--quiet` | false | подавить вывод в stdout (используется с `--output-dir`) |

**Важно:** глобальный флаг `--output text|json` пишется **до** subcommand'а: `python manage.py --output json monitor resources ...`

### Импорт CSV в таблицу (адаптер)

Загружает данные из произвольного CSV-файла (выгрузка GitLogger, LMS-экспортёра или любого другого источника) в существующую xlsx-таблицу в Nextcloud по принципу **upsert по ключу**: строки с совпадающим ключом обновляются, новые добавляются в конец, незатронутые остаются как есть. Если CSV содержит новые колонки - они добавляются в header таблицы.

Минимальный пример (GitLogger commits):
```bash
python manage.py import \
  --csv ./out.csv \
  --target /Учебные_таблицы/Группа5300_коммиты.xlsx \
  --key "commit id"
```

GitLogger issues по списку из нескольких репо - нужен композитный ключ:
```bash
python manage.py import \
  --csv ./issues.csv \
  --target /Учебные_таблицы/Issues.xlsx \
  --key "repository name" --key number
```

Moodle экспортёр (`moodle_exporter.py`) - CSV с разделителем `;` и pandas-индексной колонкой:
```bash
python manage.py import \
  --csv ./moodle_course_12345.csv \
  --target /Учебные_таблицы/Курс12345_оценки.xlsx \
  --key username \
  --separator ";" \
  --skip-columns 1
```

Все флаги:

| Флаг | Обязателен | По умолчанию | Описание |
|---|---|---|---|
| `--csv PATH` | да | - | путь к локальному CSV-файлу |
| `--target PATH` | да | - | путь к xlsx внутри Nextcloud (например `/Учебные_таблицы/Группа.xlsx`) |
| `--key COL` | да | - | имя колонки-ключа; повторите флаг для составного ключа |
| `--sheet NAME` | нет | первый лист | имя листа внутри xlsx |
| `--separator C` | нет | `,` | разделитель полей в CSV (`;` для pandas/Moodle) |
| `--encoding ENC` | нет | `utf-8` | кодировка CSV |
| `--skip-columns N` | нет | `0` | сколько ведущих колонок CSV отбросить (полезно для pandas-index) |
| `--create-if-missing` | нет | выкл. | создать пустой xlsx (и недостающие папки) если target не существует; без флага отсутствующий target - ошибка |

Создание target вместе с импортом (если файла ещё нет) - флаг `--create-if-missing` создаст пустой xlsx и недостающие промежуточные папки:
```bash
python manage.py import --csv ./out.csv \
  --target /Учебные_таблицы/Новая_папка/новая_таблица.xlsx \
  --key "commit id" \
  --create-if-missing
```

**Ограничения**: 
- По умолчанию target xlsx должен существовать в Nextcloud (создайте через UI, через `manage.py upload`, или используйте `--create-if-missing`).
- В момент импорта файл не должен быть открыт в OnlyOffice - иначе либо import получит HTTP 423 (locked), либо параллельные правки в редакторе будут перезаписаны при PUT.
- Адаптер не парсит числа/даты - значения хранятся как строки, OnlyOffice сам определит формат при отображении.
