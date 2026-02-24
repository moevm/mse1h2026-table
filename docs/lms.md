# LMS.md

## Назначение

Набор скриптов и утилит для экспорта данных из образовательных платформ (Moodle, Stepik, DIS/Slides-checker и др.), скачивания артефактов по ссылкам, загрузки результатов в Google Sheets и на Яндекс.Диск, а также для подготовки CSV/XLSX отчётов для дальнейшей автоматической обработки.

# 1. Структура репозитория

* `common_grade_export/` - общая логика: экспортеры, утилиты для Google Sheets и Yandex Disk, Dockerfile.

  * `src/exporters/` - `moodle_exporter.py`, `stepik_exporter.py`, `dis_exporter.py`
  * `src/utils/` - парсеры аргументов, helper-утилиты, менеджеры для Google / Yandex.
* `stepik_progress_export/` - отдельная реализация экспорта прогресса Stepik (OAuth client credentials flow).
* `export_from_links/` - скачивание файлов по прямым ссылкам, Google Drive, Mail.ru и т.д.
* `google_export/` - парсинг/экспорт специфичных данных (developer.google.com badges и т.п.).
* `rating_export/` - экспорт рейтингов в HTML (генерация страниц/индексов для студентов).
* `requirements.txt` в подпроектах и Dockerfile в `common_grade_export/`.
* `system_cred.example.json` - пример формата централизованных credentials.

# 2. Главные сценарии использования (точки входа)

1. **Экспорт оценок из Moodle** - `common_grade_export/src/exporters/moodle_exporter.py`
2. **Экспорт прогресса из Stepik** - `stepik_progress_export/main.py` или `common_grade_export/src/exporters/stepik_exporter.py`
3. **Экспорт/проверка через DIS / slides-checker** - `common_grade_export/src/exporters/dis_exporter.py`
4. **Скачивание файлов по ссылкам** - `export_from_links/main.py`
5. **Парсер developer.google.com badges** - `google_export/main.py` (парсер бейджей / метаданных)
6. **Экспорт рейтинга в moevm wiki** - `rating_export/main.py`
7. **Выгрузка в Google Sheets / Яндекс.Диск** - утилиты в `common_grade_export/src/utils/`

# 3. Формат входов (что ожидают скрипты)

### Общие

* CLI-аргументы (см. примеры ниже).
* JSON-файл централизованных учётных данных (`system_cred.json`) - в репозитории есть `system_cred.example.json`.
* JSON-файл для moevm wiki (`config.json`).
* Google Service Account JSON (файл ключа) для работы с Google Sheets.
* Для загрузки на Яндекс.Диск - OAuth-токен.

### Пример `system_cred.example.json`

```json
{
    "moodle": "token",
    "dis": "access_token",
    "stepik": {
        "client_id": "client_id",
        "client_secret": "client_secret"
    }
}
```

### Пример `config.json`

```json
{
    "google": {
        "credentials_file": "credentials.json"
    },
    "export": [
        {
            "spreadsheet_key": "table_id",
            "worksheet_name": "Информатика",
            "outdir_path": "./html/grade/first_course/",
            "subject": "Информатика",
            "common_columns": {
                "name": "ФИО",
                "login": "Логин на e.moevm.info",
                "group": "Группа"
            },
            "header_row": 2,
            "published_columns": ["G:I", "O:Q", "T:V"]
        }
    ]
}
```

### `rating_export/main.py` - не CLI, всё в json

* `config.json` с полями:

  * `google.credentials_file` - путь к Google service account JSON (credentials.json).
  * список `export` объектов - каждый объект описывает:

    * `spreadsheet_key` - id Google таблицы,
    * `worksheet_name` - имя листа,
    * `outdir_path` - путь, куда записать HTML (директория вывода),
    * `subject` - название дисциплины,
    * `common_columns` - mapping названий колонок (`name`, `login`, `group`) на реальные заголовки в таблице,
    * `header_row` - индекс строки заголовков (0-based),
    * `published_columns` - список интервалов колонок для публикации (например `"G:I"`, т.е. диапазон колонок).
* Для работы нужен доступ service account к Google Sheet (service account email должен иметь права чтения).

## Основные CLI-опции (по подпроектам)

### `moodle_exporter.py`

* `--url` - базовый URL Moodle.
* `--moodle_token` - Specify moodle token.
* `--course_id` - id курса / список course_id.
* `--csv_path` - путь выходного CSV (обязательно).
* `--google_token` - путь к Google service account JSON (опционально).
* `--table_id`, `--sheet_id`/`--sheet_name` - для выгрузки в Google Sheets (опционально).
* `--yandex_token`, `--yandex_path` - для загрузки на Я.Диск (опционально).
* `--percentages` - если подается, то оценки будут выведены в процентах (опционально).

### `stepik_progress_export/main.py`

* `--client_id` - Stepik OAuth client id (https://stepik.org/oauth2/applications/).
* `--client_secret` - Stepik OAuth client secret (https://stepik.org/oauth2/applications/).
* `--course_id` - id курса (отсюда: https://stepik.org/course/63054/syllabus).
* `--class_id` - id класса (отсюда: https://stepik.org/class/33587/gradebook).
* `--csv_path` - выходной CSV.
* `--yandex_token`, `--yandex_path` - опционально (отсюда: https://oauth.yandex.ru/client/new).

### `dis_exporter.py`

* `--google_token` - путь к файлу с токеном Google.
* `--checker_token` - token для slides-checker / DIS.
* `--checker_filter` - фильтр по заданиям/пользователям.
* `--csv_path` - путь выходного CSV.
* `--table_id`, `--sheet_id`/`--sheet_name` - для выгрузки в Google Sheets (опционально).
* `--yandex_token`, `--yandex_path` - опционально.

### `export_from_links/main.py`

* `--table_link` - обязательный. Ссылка на Google Spreadsheet (публичный/доступный для чтения лист), из которой скрипт парсит HTML-таблицу.
* `--credentials` - обязательный. Токен (строка) для Яндекс.Диска. (Передаётся в `yadisk.Client(token=args.credentials)`.)
* `--prefix_column_name` - обязательный. Имя столбца в таблице, значения которого используются как префикс в имени скачиваемого файла.
* `--download_column_name` - обязательный. Имя столбца, содержащего ссылки на файлы для скачивания.
* `--cloud_directory_path` - обязательный. Путь на Яндекс.Диске, в который загружаются полученные файлы (например `/exports/2026/`).

### `google_export/main.py`

* `-o`, `--output` - название выходного CSV-файла.
* `-i`, `--ids_file` - файл со списком id пользователей (по одному id на строку). Значения будут включены в колонку `name` выходного CSV.
* `-k`, `--key` - API-ключ (берётся из dev-консоли; параметр `key` в GET-запросах).
* `-c`, `--curl_args` - ключ для нахождения id пользователя, если оно представляется как строковое (аналогично предыдущему, фильтровать по GetProfile, POST-запрос, ключ в header'ах 'X-Goog-Api-Key').
* `-t`, `--timeout` - таймаут одного запроса (в секундах).
* `-r`, `--repeat` - число повторных попыток (retry) при ошибках (по умолчанию 10).
* `--google_token` - путь до Google service account JSON для выгрузки в Google Sheets (опционально).
* `--table_id` - id Google таблицы (если нужно выгрузить туда) (опционально).
* `--sheet_id` - id листа в таблице (опционально). 
* `--input_sheet_id` - id листа в гугл таблице.
* `--input_column_skip` / `--input_column_number` - опции для пропуска/выбора столбцов при чтении.

# 4. Формат выходов

### `moodle_exporter.py`

* **Формат:** CSV (UTF-8), опционально `.xlsx` (openpyxl).
* **Разделитель:** в коде часто используется `sep=";"` (точка с запятой).
* **Типичные колонки (пример, зависит от конфигурации):**

  ```
  placeholder
  ```

  Поля активности формируются динамически (названия колонок соответствуют активностям курса).
* **Опции вывода:** прямой файл `--csv_path`; при `--google_token`/`--table_id` данные пишутся в Google Sheets; при `--yandex_token`/`--yandex_path` - файл загружается на Яндекс.Диск.
* **Особенности:** даты/времена - обычно ISO-подобные строки; оценки можно выводить в процентах при флаге `--percentages`. Контракт зависит от набора `options`/конфигурации (колонки могут отличаться между запусками).

### `stepik_progress_export/main.py` (и `stepik_exporter.py`)

* **Формат:** CSV (UTF-8).
* **Типичные колонки (пример):**

  ```
  placeholder
  ```
* **Опции вывода:** `--csv_path` для локального файла; поддерживается загрузка на Яндекс.Диск (`--yandex_token/--yandex_path`) и (в общих экспортёрах) - запись в Google Sheets.
* **Особенности:** шаги/баллы/процент прогресса - числовые поля; возможна пагинация API и различия в полях в зависимости от версии Stepik API.

### `dis_exporter.py` (slides-checker / DIS)

* **Формат:** CSV (UTF-8).
* **Пример колонок:**

  ```
  placeholder
  ```
* **Опции вывода:** `--csv_path`; опционально Google Sheets / Yandex (через те же аргументы).
* **Особенности:** поля `checker_status` и `comments` содержат результаты автоматической проверки; время отправки - timestamp строкой.

### `export_from_links/main.py`

* **Форматы выходов:**

  * **Файлы** - бинарные/оригинальные файлы, скачанные по ссылкам; сохраняются локально с именем `"{prefix}_{download_column_name}.{ext}"` (где `prefix` - значение из таблицы).
  * **Отчёт/лог** - файл `YY_MM_DD_HH:MM_download_report.log` (лог/отчёт о попытках скачивания и загрузке).
* **Дополнительно:** после скачивания файлы загружаются на Яндекс.Диск в `--cloud_directory_path` (если токен валиден).
* **Особенности:** расширение определяется через `filetype.guess(...)` с fallback; имена файлов могут требовать санации (символы/длина). Скрипт не возвращает единый CSV с метаданными по умолчанию - лог содержит сводную информацию (успех/ошибка, http_status, путь).

### `google_export/main.py` (developer.google.com badges parser)

* **Формат:** CSV (UTF-8).
* **Типичные колонки (пример/рекомендация):**

  ```
  placeholder
  ```

  (структура зависит от того, какие поля парсер извлекает)
* **Опции вывода:** `--output` локальный CSV; при `--google_token` + `--table_id` - выгрузка в Google Sheets.
* **Особенности:** использование API key / curl args влияет на то, какие поля доступны; возможны частичные/просроченные данные для некоторых профилей.

### `rating_export/main.py` (генератор страниц для moevm wiki)

* **Формат:** статический HTML (папка).
* **Структура вывода:**

  * Для каждого студента - директория `outdir_path/<student_hash>/index.html` (и сопутствующие файлы).
  * Индексная страница `moevm_all_student_secret_page_<YYYY>.html` в корне `outdir_path`.
* **Содержимое страниц:** табличный/версточный вывод выбранных колонок (указанных в `published_columns`), общая информация (`name`, `login`, `group`) и ссылки на ресурсы/файлы.
* **Особенности:** имя страницы/путь формируется через хеш логина (для «секретных» ссылок); файлы создаются и готовы к размещению на статическом хосте или в вики.

---

### Общие выходы / вспомогательные артефакты

* **Google Sheets:** многие экспортёры поддерживают опциональную запись в Google Sheets (через `pygsheets`/`gspread`) - таблица по `table_id`, лист по `sheet_id`/`sheet_name`.
* **Яндекс.Диск:** при наличии `--yandex_token` результат (CSV/файлы) может быть загружен на указанный путь `--yandex_path`/`--cloud_directory_path`.
* **Логи:** каждый подпроект пишет логи (stdout и/или файловые логи) - используйте их как дополнительный артефакт при CI/отладке.
* **Коды возврата:** экспортёры завершат с non-zero exit code при критических ошибках (авторизация, недоступность API) - ожидать это для CI.


# 5. Зависимости / рекомендованное окружение

* Рекомендованная версия Python: **3.10–3.13** (Dockerfile использует `python:3.13-slim`).
* Установить зависимости для подпроекта:

```bash
pip install -r common_grade_export/requirements.txt
# или
pip install -r export_from_links/requirements.txt
# или
pip install -r google_export/requirements.txt
# или
pip install -r stepik_progress_export/requirements.txt
```

* Dockerfile находится в `common_grade_export/` и `stepik_progress_export/`.

# 6. Секреты и права доступа

* **Google Service Account JSON** - для доступа к Google Sheets (файл, передать через `--google_token` или монтировать в контейнер).
* **Moodle webservice token** - для REST API Moodle (`token`).
* **Stepik OAuth (client_id + client_secret)** - для получения access token (client_credentials).
* **DIS / slides-checker token** - `checker_token`.
* **Yandex OAuth token** - для загрузки на Яндекс.Диск.
* **API key** для `google_export` (developer.google.com) - передаётся как `--key`.

# 7. Примеры запуска и типовые команды

### Пример - Moodle экспорт

```bash
python3 common_grade_export/src/exporters/moodle_exporter.py \
  --url "https://e.moevm.info" \
  --moodle_token "TOKEN" \
  --course_id 12345 \
  --csv_path ./out/moodle_course_12345.csv
```

### Пример - Stepik

```bash
docker-compose run parser \
  --client_id xxx \
  --client_secret xxx \
  --course_id 63054 \
  --class_id 33587 \
  --csv_path ./results/kek.csv \
  --yandex_token xxx \
  --yandex_path kek.csv
```

Или локально:

```bash
python3 stepik_progress_export/main.py \
  --client_id xxx \
  --client_secret xxx \
  --course_id 63054 \
  --class_id 33587 \
  --csv_path ./results/kek.csv \
  --yandex_token xxx \
  --yandex_path kek.csv
```

### Пример - DIS / slides-checker

```bash
python3 common_grade_export/src/exporters/dis_exporter.py \
  --checker_token TOKEN \
  --csv_path ./out/dis_results.csv
```

### Пример - export_from_links

```bash
python3 export_from_links/main.py \
  --table_link "https://docs.google.com/spreadsheets/d/XXXX/edit#gid=1" \
  --credentials "YANDEX_OAUTH_TOKEN" \
  --prefix_column_name "student_login" \
  --download_column_name "submission_link" \
  --cloud_directory_path "/exports/course_123/"
```

### Пример - google_export

```bash
docker run -it --entrypoint python3 <имя контейнера> main.py -i 'ids' -o 'fname.csv' -k 'ключ1' -c 'ключ2' -t 0.1"
```

Или локально:

```bash
python3 main.py -i 'ids' -o 'fname.csv' -k 'ключ1' -c 'ключ2' -t 0.1
```

### Docker - build & run (common exporter)

```bash
cd common_grade_export

# Установить нужные переменные окружения
export MOODLE_TOKEN="moodle_token"
export DIS_ACCESS_TOKEN="dis_token"
export STEPIK_CLIENT_ID="stepik_client_id"
export STEPIK_CLIENT_SECRET="stepik_client_secret"

export TABLE_ID="google_table_id"
export SHEET_ID="google_sheet_id"
export EXPORTER_GOOGLE_CONF="/absolute/path/to/google_service_account.json"

./run.sh
```