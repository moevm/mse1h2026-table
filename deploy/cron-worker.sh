#!/bin/bash

# Настройки интервалов
CRON_INTERVAL=300   # 5 минут
SYNC_INTERVAL=10    # 10 секунд
NEXTCLOUD_PATH="/var/www/html"

# Переменные состояния
LAST_CRON_RUN=0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Функция для выполнения php с нужными параметрами, чтобы не было лишних ворнингов
php_occ() {
    # -d memory_limit=512M убирает ошибку "Failed to set memory limit"
    php -d memory_limit=512M "$NEXTCLOUD_PATH/occ" "$@"
}

log "Waiting for Nextcloud installation..."
until php_occ status 2>/dev/null | grep -q "installed: true"; do
    sleep 5
done

while true; do
    START_TIME=$(date +%s)

    # 1. ПРИОРИТЕТ: Синхронизация форм
    # Получаем вывод и очищаем его: оставляем только то, что начинается с '[' (начало JSON массива)
    RAW_OUTPUT=$(php_occ background-job:list --output=json 2>/dev/null)
    CLEAN_JSON=$(echo "$RAW_OUTPUT" | sed -n '/^\[/,$p')

    # Проверяем, не пустой ли JSON и валиден ли он
    if echo "$CLEAN_JSON" | jq -e '. == []' >/dev/null 2>&1; then
        : # Задач нет, ничего не делаем
    elif [ -n "$CLEAN_JSON" ]; then
        # Фильтруем нужные задачи
        JOBS=$(echo "$CLEAN_JSON" | jq -c '.[] | select(.class == "OCA\\Forms\\BackgroundJob\\SyncSubmissionsWithLinkedFileJob")' 2>/dev/null)

        if [ -n "$JOBS" ]; then
            echo "$JOBS" | while read -r JOB; do
                JOB_ID=$(echo "$JOB" | jq -r '.id')
                ARG=$(echo "$JOB" | jq -r '.argument')

                log "EXPORT: Form (JOB_ID: $JOB_ID, ARG: $ARG)"

                # Выполняем конкретную задачу
                OUTPUT=$(php_occ background-job:execute "$JOB_ID" 2>&1)
                if [ $? -eq 0 ]; then
                    log "SUCCESS: Job $JOB_ID completed."
                else
                    log "ERROR: Job $JOB_ID. Output: $OUTPUT"
                fi
            done
        fi
    fi

    # 2. ТАЙМЕР: Стандартный cron.php
    CURRENT_TIME=$(date +%s)
    if [ $((CURRENT_TIME - LAST_CRON_RUN)) -ge "$CRON_INTERVAL" ]; then
        log "CRON START: Scheduled cron.php"
        php -d memory_limit=512M -f "$NEXTCLOUD_PATH/cron.php"
        LAST_CRON_RUN=$(date +%s)
        log "CRON COMPLETED: Scheduled cron.php"
    fi

    # 3. КОРРЕКЦИЯ ТАЙМЕРА
    END_TIME=$(date +%s)
    SLEEP_TIME=$((SYNC_INTERVAL - (END_TIME - START_TIME)))
    [ "$SLEEP_TIME" -le 0 ] && SLEEP_TIME=1
    sleep "$SLEEP_TIME"
done
