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

3. По умолчанию Nextcloud (с подключённым OnlyOffice) будет доступен на порту 80.

   При необходимости порт можно изменить через переменную `NEXTCLOUD_PORT` в файле `.env`.

4. Для остановки:
   ```bash
   docker compose down
   ```

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
