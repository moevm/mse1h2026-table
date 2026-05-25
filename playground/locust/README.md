# Locust playground (issue #88)

Учебные сценарии Locust для освоения инструмента. **Это не нагрузочное тестирование нашей системы** — сценарии стучат в публичный echo-сервис [httpbin](https://httpbin.org/) (или локально через `kennethreitz/httpbin`). Реальный нагрузочный прогон против Nextcloud живёт в [`table/loadtest/`](../../table/loadtest/) и запускается через `python manage.py loadtest run`.

## Запуск

```bash
# В отдельной консоли — поднять httpbin
docker run -d --name httpbin -p 8088:80 kennethreitz/httpbin

cd playground/locust
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Все три сценария подряд против httpbin
bash run_headless.sh http://localhost:8088
```

## Сценарии

| Файл | Демонстрирует |
|---|---|
| `scenarios/single_request.py` | Базовый `HttpUser` с одной задачей, проверка тела ответа |
| `scenarios/chain.py` | `SequentialTaskSet` — цепочка login → create → read с передачей токена между шагами |

Артефакты прогона (CSV + HTML) — в `results/`.
