# Loadtest

Нагрузочное тестирование стека через [Locust](https://locust.io/).

## Запуск

```bash
cd table

# 1. Один раз: установить locust
pip install -r loadtest/requirements.txt

# 2. Один раз: засеять тестовых пользователей
python manage.py users csv-create loadtest/users.csv

# 3. Прогон
python manage.py loadtest run --scenario stepped
```

Стек должен быть поднят (`python manage.py deploy up`) и здоров (`python manage.py deploy status --wait`).

## Сценарии

| Имя | Файл | Профиль |
|---|---|---|
| `stepped` | `scenarios/stepped.py` | 50 → 100 → 200 → 300 пользователей за 10 минут. PROPFIND по WebDAV + OCS user-status. |
| `smoke` | `scenarios/smoke.py` | Тот же набор запросов без `LoadTestShape` — управляется флагами `--users`/`--spawn-rate`/`--run-time`. Для быстрой проверки пайплайна. |

## Флаги `loadtest run`

| Флаг | По умолчанию | Что делает |
|---|---|---|
| `--scenario` | `stepped` | Имя сценария из таблицы выше |
| `--host` | URL из `deploy/.env` | Целевой Nextcloud для locust (`--host` у locust'а) |
| `--users` | из shape сценария | Override максимума одновременных юзеров (игнорируется сценариями с `LoadTestShape`) |
| `--spawn-rate` | из shape | Скорость спавна |
| `--run-time` | из shape | Общая длительность (`60s`, `5m`) |
| `--results-dir` | `loadtest/results/<timestamp>/` | Куда сложить CSV-статы и HTML-отчёт |
| `--password` | `Leti2026!!` | Пароль тестовых юзеров (env `LOADTEST_PASSWORD`) |
| `--user-prefix` | `s` | Префикс логинов студентов |
| `--user-max` | `350` | Верхняя граница диапазона юзеров `s001..sNNN` |

После прогона в `--results-dir` появятся:
- `stats_stats.csv` — агрегированная статистика по эндпоинтам
- `stats_failures.csv` — ошибки
- `stats_stats_history.csv` — таймлайн
- `report.html` — итоговый HTML-отчёт от locust

`manage.py loadtest run --output json` печатает headline-числа (total / failures / avg / p95 / RPS) в stdout — удобно для CI или скрипта.

## Серверные метрики (CPU/RAM)

Locust меряет только клиентскую сторону. Чтобы дополнить серверной — запустить параллельно `monitor resources` и склеить timeline скриптом:

```bash
# терминал 1
./bin/table-cli monitor resources --interval 5 --count 145 --quiet \
    --output-dir /abs/path/to/monitor_dir

# терминал 2 (через 2-3 секунды)
python manage.py loadtest run --scenario stepped

# когда оба закончатся
python loadtest/analyze_resources.py \
    --monitor-dir /abs/path/to/monitor_dir \
    --results-dir loadtest/results/<timestamp>
```

Скрипт делит таймлайн на стадии (50/100/200/300 юзеров + baseline/cooldown) и выводит среднее/пиковое CPU и RAM на каждый контейнер, плюс производные «MB на воркер FPM» и «юзеров на ядро».

Эталонный анализ - в ветке `reports`.
