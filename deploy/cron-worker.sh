#!/bin/bash

CRON_INTERVAL=300   # 5 минут
SYNC_INTERVAL=10    # 10 секунд
NEXTCLOUD_PATH="/var/www/html"

# Переменные состояния
LAST_CRON_RUN=0

# Обработка корректного завершения (Docker stop)
trap "echo 'Stopping worker...'; exit 0" SIGTERM SIGINT

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

php_occ() {
    php -d memory_limit=2G "$NEXTCLOUD_PATH/occ" "$@"
}

log "Waiting for Nextcloud installation..."
until php_occ status 2>/dev/null | grep -q "installed: true"; do
    sleep 5
done

log "Cron started (Sync: ${SYNC_INTERVAL}s, Cron: ${CRON_INTERVAL}s)"

while true; do
    LOOP_START=$(date +%s)

    # Синхронизация форм
    # Получаем вывод и очищаем его: оставляем только то, что начинается с '[' (начало JSON массива)
    RAW_OUTPUT=$(php_occ background-job:list --output=json 2>/dev/null)
    CLEAN_JSON=$(echo "$RAW_OUTPUT" | sed -n '/^\[/,$p')

    if [ -z "$CLEAN_JSON" ] || echo "$CLEAN_JSON" | jq -e '. == []' >/dev/null 2>&1; then
        : # Задач нет
    else
        JOBS=$(echo "$CLEAN_JSON" | jq -c '.[] | select(.class == "OCA\\Forms\\BackgroundJob\\SyncSubmissionsWithLinkedFileJob")' 2>/dev/null)

        if [ -n "$JOBS" ]; then
            echo "$JOBS" | while read -r JOB; do
                JOB_START=$(date +%s)
                JOB_ID=$(echo "$JOB" | jq -r '.id')
                ARG=$(echo "$JOB" | jq -r '.argument')

                OUTPUT=$(php_occ background-job:execute "$JOB_ID" 2>&1)
                EXIT_CODE=$?
                JOB_END=$(date +%s)
                DURATION=$((JOB_END - JOB_START))

                if [ $EXIT_CODE -eq 0 ]; then
                    log "JOB: Form (ID: $JOB_ID, ARG: $ARG) - OK (${DURATION}s)"
                else
                    log "ERROR: Job $JOB_ID failed (${DURATION}s). Output: $OUTPUT"
                fi
            done
        fi
    fi

    # Стандартный cron.php
    CURRENT_TIME=$(date +%s)
    if [ $((CURRENT_TIME - LAST_CRON_RUN)) -ge "$CRON_INTERVAL" ]; then
        CRON_START=$(date +%s)

        php -d memory_limit=2G -f "$NEXTCLOUD_PATH/cron.php" > /dev/null 2>&1

        LAST_CRON_RUN=$(date +%s)
        DURATION=$((LAST_CRON_RUN - CRON_START))
        log "CRON: System tasks completed (${DURATION}s)"
    fi

    # Коррекция таймера
    LOOP_END=$(date +%s)
    SLEEP_TIME=$((SYNC_INTERVAL - (LOOP_END - LOOP_START)))

    # Чтобы контейнер мгновенно реагировал на стоп, спим короткими отрезками
    # либо просто используем sleep, Bash прервет его при получении сигнала trap
    if [ "$SLEEP_TIME" -gt 0 ]; then
        sleep "$SLEEP_TIME" & wait $!
    else
        sleep 1 & wait $!
    fi
done
