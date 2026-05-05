FROM python:3.11-slim

# docker CLI + compose plugin нужны изнутри cli-контейнера: backup/restore/monitor
# делают `docker compose exec` для occ, pg_dump, psql, tar, sed по config.php,
# а deploy up/down/status/demo управляют compose-проектом снаружи.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && chmod a+r /etc/apt/keyrings/docker.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Код CLI не копируется в образ - bind-mount всего репо в compose-сервисе
# подкладывает manage.py и scripts/ при каждом запуске. working_dir
# задаётся в docker-compose.yml (cli service).
ENTRYPOINT ["python", "manage.py"]
