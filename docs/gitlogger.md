# GITLOGGER.md

## Назначение

Скрипт **github_repo_commitment_calc** собирает и агрегирует данные репозиториев (коммиты, contributors, PR, issues, wiki, workflow runs, invites) и экспортирует их в CSV-файлы или Google Sheets. Цель - предоставить экспортные контракты, инструкции запуска и требования для интеграции.

---

## 1. Входы (что ожидает)

* CLI / аргументы:

  * `-h`, `--help` - Показать справку и выйти.
  * `-c`, `--commits` - Логирование commits.
  * `-i`, `--issues` - Логирование issues.
  * `-p`, `--pull_requests` - Логирование pull requests.
  * `--pr_comments` - Выгружать комментарии к pull requests.
  * `-s` - Начальная дата / фильтр (например "2024-01-01")..
  * `-f` - Конечная дата / фильтр.
  * `-b` - Анализ конкретной ветки (например "main").
  * `--invites` - Логирование непринятых приглашений в репо.
  * `-w`, `--wikis` - Логирование вики-репозиториев.
  * `--contributors` - Логирование контрибьюторов.
  * `--workflow_runs` - Сбор информации о workflow runs (GitHub Actions).
  * `--forks_include` - Включать форки в анализ (по умолчанию — нет).
  * `--download_repos PATH_DREPO` - путь к директории, куда сохраняются wiki-репозитории (используется совместно с `--wikis`)
  * `-t TOKEN` | `--tokens TOKENS` - Git token (GitHub Personal Access Token) или путь к файлу с токенами.
  * `-l LIST`, `--list LIST` - путь к файлу со списком репозиториев (каждая строка: `owner/repo`).
  * `-o OUT`, `--out OUT` - путь к выходному CSV.
  * `--table_id TABLE_ID`, `--sheet_name SHEET_NAME`, `--google_token TOKEN.json`, `--clear_sheet` - параметры для выгрузки в Google Sheets.
  * `--base_url` - base URL для Forgejo (self-hosted).

* Формат файла репозиториев: одна строка - `owner/repo`. Т.е. файл выглядит следующим образом:
```
owner1/repo1
owner2/repo2
```
* Каждый токен записывается в отдельную строку. Токены должны быть привзязаны к разным github аккаунтам. Токены, привязанные к одному аккаунту имеют общий rate_limit.

---

## 2. Выходы (что отдаёт)

* Основной выход - CSV-файл. 

Для режима `commits` ожидается заголовок и порядок колонок:

```
repository name,author name,author login,author email,date and time,changed files,commit id,branch,additions,deletions
```

* Особенности полей:

  * `changed files` - список файлов в одной ячейке; разделитель внутри поля - `; ` (точка с запятой и пробел).
  * `date and time` - ISO 8601 с часовой зоной (например `2026-02-13T23:38:14+03:00`).

* Опционально: выгрузка в Google Sheets при передаче `--table_id`/`--sheet_id` и `--google-token`.

Для режима `issues` ожидается заголовок и порядок колонок:

```
repository name,number,title,state,task,created at,creator name,creator login,creator email,closer name,closer login,closer email,closed at,comment body,comment created at,comment author name,comment author login,comment author email,assignee story,connected pull requests,labels,milestone
```

Для режима `pull_requests` ожидается заголовок и порядок колонок:

```
repository name,title,id,state,commit into,commit from,created at,creator name,creator login,creator email,changed files,comment body,comment created at,comment author name,comment author login,comment author email,merger name,merger login,merger email,source branch,target branch,assignee story,related issues,labels,milestone
```

Для режима `invites` ожидается заголовок и порядок колонок:

```
repository name,invited login,invite creation date,invitation url
```

Для режима `wikis` ожидается заголовок и порядок колонок:

```
repository name,author name,author login,datetime,page,action,revision id,added lines,deleted lines
```

Для режима `contributors` ожидается заголовок и порядок колонок:

```
repository name,login,name,email,url,permissions,total commits,node id,type,bio,site admin
```

---

## 3. Зависимости и окружение

* Рекомендуемая версия Python: **3.10–3.11** (избежать предупреждений `pyforgejo`/`pydantic` при Python ≥ 3.14).
* Основные зависимости (из `requirements.txt`):

  * `GitPython`, `PyGithub`, `pygsheets`, `pandas`, `pytz`, `requests`, `pyforgejo`, `isodate`.
* Dockerfile включён - опция контейнеризации.

---

## 4. Секреты и права доступа

* **GitHub PAT(s)** - требуется scope `repo` для приватных репозиториев;
* **Google service account JSON** - если используется выгрузка в Google Sheets;
* **Forgejo token** + `--base_url` - при использовании self-hosted Forgejo.


## 5. Примеры запуска

### Установка зависимостей

Для корректной работы приложения необходимо установить зависимости, указанные в `requirements.txt`, чтобы это сделать
используйте команду:

```commandline
pip install -r requirements.txt
```

### Docker run

1. Build via:
``` bash
docker build -t checking_repo .
```

2. Run via:
``` bash
docker run -v $(pwd)/output:/app/output checking_repo [--invites] [--commits] [--etc...] -t <insert_token> -l <insert_list> -o ./output/res.csv
```

### Обычный запуск

1. Cобрать коммиты в CSV:
```bash
python3 main.py -c -t YOUR_GH_TOKEN -l repo.txt -o out.csv
```

2. Выгрузка в Google Sheets:
```bash
python3 main.py -c -t YOUR_GH_TOKEN -l repo.txt \
  --table_id TABLE_ID \
  --sheet_name SHEET_NAME \
  --google_token /path/to/service_account.json
```
