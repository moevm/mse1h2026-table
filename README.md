# mse1h2026-table

## Установка и запуск
На текущий момент подготовлены конфигурации для развертывания двух предварительно отобранных решений.

Конфигурации размещены в директории playground в соответствующих подразделах.

---
### Nextcloud + OnlyOffice

1. Перейти в директорию развертывания:
   ```bash
   cd playground/onlyoffice-nextcloud/deploy
   ```

2. Запустить контейнеры:
   ```bash
   docker compose up -d
   ```

3. По умолчанию Nextcloud (с подключённым OnlyOffice) доступен на порту `8080`.

   При необходимости порт можно изменить через переменную `NEXTCLOUD_PORT` в файле `.env`.

4. Для остановки:
   ```bash
   docker compose down
   ```

#### Интеграция Nextcloud Forms -> Windmill

После запуска стека в `playground/onlyoffice-nextcloud/deploy/docker-compose.yml` автоматически поднимаются сервисы:

- `windmill-db` (PostgreSQL для Windmill)
- `windmill` (Windmill server)
- `windmill-worker` (исполнитель workflow)

Далее настройка OAuth-подключения в Windmill:

1. Откройте Windmill.
2. Войдите в workspace admin.
3. Перейдите `Settings -> Workspace -> Native Triggers`.
4. Для интеграции Nextcloud укажите `Nextcloud base URL`.
5. Для получения `Client ID` и `Client secret` необходимо выполнить скрипт:
```
chmod +x ./create_windmill_oauth.sh
./create_windmill_oauth.sh
```
6. Вставьте `Client ID` и `Client secret` из Nextcloud OAuth-клиента и нажмите `Save configuration`.
6. Нажмите `Connect`.
7. Подтвердите доступ учеткой Nextcloud и дождитесь возврата в Windmill.
8. Убедитесь, что в интерфейсе Windmill статус подключения стал `Connected`.

Проверка сервисов Docker:
```bash
cd playground/onlyoffice-nextcloud/deploy
docker compose ps
```

Если стек уже был поднят до изменений, примените интеграцию вручную:
```bash
cd playground/onlyoffice-nextcloud/deploy
docker compose run --rm nextcloud-init
```

Если в Windmill в консоли браузера видите `400 Bad Request` на эндпоинтах вида
`/api/w/admins/workspaces/used_triggers` или
`/api/w/admins/native_triggers/integrations/nextcloud/exists`, и в логах есть
`permission denied to set role "windmill_admin"`, выполните разово:
```bash
cd playground/onlyoffice-nextcloud/deploy
docker compose exec -T windmill-db psql -U postgres -d windmill -c "GRANT windmill_admin TO windmill;"
docker compose exec -T windmill-db psql -U postgres -d windmill -c "GRANT windmill_user TO windmill;"
docker compose restart windmill windmill-worker
```

#### Проверка, что интеграция реально работает

1. Проверить статус подключения в Windmill:
   - `Settings -> Workspace -> Native Triggers -> Nextcloud`
   - Статус должен быть `Connected`.
2. Создать тестовый flow:
   - `New Flow` -> блок `Triggers` -> `+` -> `Nextcloud`.
   - В списке событий должны быть доступны события (без ошибок `No events available`).
3. Выполнить тест события:
   - Отправить тестовый ответ в Nextcloud Forms.
   - Убедиться, что в Windmill у flow появился новый `Run`.
4. Если у flow нет запусков:
   - проверить логи Windmill: `docker logs --tail 200 windmill-server`
   - проверить, что нет ошибок `Failed to exchange code for token`.

---

### Seafile + OnlyOffice

1. Перейти в директорию развертывания:
   ```bash
   cd playground/onlyoffice-seafile/deploy
   ```

2. Запустить контейнеры:
   ```bash
   docker compose -f seafile-server.yml -f seadoc.yml -f caddy.yml up -d
   ```

3. По умолчанию сервис будет доступен на порту `8081`.

   Изменение порта выполняется через переменную `HTTP_PORT` в файле `.env`.

4. Для остановки:
   ```bash
   docker compose -f seafile-server.yml -f seadoc.yml -f caddy.yml down
   ```

## Проверка работоспособности
Инструкции по проверке работоспособности проекта (основной функциональности и результатов).
TODO
