import os
import glob
import logging
import requests
from urllib.parse import quote

# Настройка логирования: выводит сообщения в реальном времени в консоль
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


def _ensure_cloud_directory(session, base_url, dest_path):
    """
    Автоматическое создание структуры папок.

    Механика:
    1. Разбивает путь (напр. /A/B/C) на части.
    2. Для каждой части проверяет существование через метод PROPFIND.
    3. Если папка не найдена (404), создает её методом MKCOL.
    """
    parts = [p for p in dest_path.strip('/').split('/') if p]
    current_path = ""

    for part in parts:
        current_path += f"/{part}"
        # quote() нужен для корректной передачи кириллицы и пробелов в URL
        full_url = f"{base_url.rstrip('/')}{quote(current_path)}"

        # Запрашиваем свойства объекта (Depth 0 - только сама папка)
        resp = session.request("PROPFIND", full_url, headers={"Depth": "0"},
                               timeout=REQUEST_TIMEOUT)

        if resp.status_code == 404:
            logger.info(f"Путь {current_path} отсутствует. Создание...")
            mkcol_resp = session.request("MKCOL", full_url,
                                         timeout=REQUEST_TIMEOUT)
            if mkcol_resp.status_code != 201:
                logger.error(f"Не удалось создать директорию {current_path}")
                return False
    return True


def upload_xlsx(session, file_path, dest_folder, config,
                name=None, overwrite=True):
    """
    Алгоритм загрузки одного файла в облако.

    Процесс разбит на 3 этапа:
    1. Подготовка папок назначения.
    2. Проверка существования файла для реализации логики перезаписи.
    3. Передача данных методом PUT.
    """
    user = config.get('user')
    # Базовый эндпоинт для работы с файлами пользователя в Nextcloud
    dav_url = f"{config.get('url').rstrip('/')}/remote.php/dav/files/{user}"

    if not os.path.exists(file_path):
        return {"file": file_path, "status": "error",
                "reason": "Local file not found"}

    if not file_path.lower().endswith('.xlsx'):
        return {"file": file_path, "status": "error",
                "reason": "File is not .xlsx"}

    # Формируем имя: используем кастомное или берем оригинальное из пути
    file_name = name if name else os.path.basename(file_path)
    remote_file_path = f"{dest_folder.strip('/')}/{file_name}"
    full_upload_url = f"{dav_url}/{quote(remote_file_path)}"

    # ЭТАП 1: Гарантируем наличие целевой папки
    if not _ensure_cloud_directory(session, dav_url, dest_folder):
        return {"file": file_name, "status": "error",
                "reason": "Directory creation failed"}

    # ЭТАП 2: Проверка наличия файла в облаке перед загрузкой
    check = session.request("PROPFIND", full_upload_url,
                            headers={"Depth": "0"},
                            timeout=REQUEST_TIMEOUT)

    # Статус 207 (Multi-Status) в WebDAV говорит о том, что файл существует
    if check.status_code == 207:
        if not overwrite:
            logger.info(
                f"Пропуск: {file_name} уже существует (overwrite=False)")
            return {"file": file_name, "status": "skipped",
                    "reason": "Already exists"}
        logger.warning(
            f"Файл {file_name} существует. Будет выполнена перезапись.")

    # ЭТАП 3: Загрузка тела файла
    try:
        with open(file_path, 'rb') as f:
            # Метод PUT сохраняет данные по указанному пути
            resp = session.put(full_upload_url, data=f,
                               timeout=REQUEST_TIMEOUT)

        if resp.status_code in [201, 204]:
            return {
                "file": file_name,
                "status": "completed",
                "remote_path": remote_file_path
            }
        return {"file": file_name, "status": "error", "code": resp.status_code}
    except Exception as e:
        return {"file": file_name, "status": "error", "reason": str(e)}


def upload_batch(config, file_path=None, dir_path=None,
                 dest="/", custom_name=None, overwrite=True):
    """
    Координатор загрузки.
    Обеспечивает работу через одну HTTP-сессию для ускорения (Keep-Alive).
    """
    files_to_process = []

    if file_path and dir_path:
        raise ValueError(
            "Одновременное использование --file и --dir запрещено")

    # Определяем список файлов для обработки
    if file_path:
        files_to_process.append((file_path, custom_name))
    elif dir_path:
        xlsx_files = glob.glob(os.path.join(dir_path, "*.xlsx"))
        for f in xlsx_files:
            files_to_process.append((f, None))

    if not files_to_process:
        return {"error": "Нет .xlsx файлов для загрузки"}

    results = []
    # Используем сессию для повторного использования TCP-соединения
    with requests.Session() as session:
        session.auth = (config.get('user'), config.get('pass'))

        # ОПТИМИЗАЦИЯ: Проверяем/создаем директорию один раз перед циклом
        user = config.get('user')
        dav_url = f"{config.get('url').rstrip('/')}/remote.php/dav/files/{user}"
        if not _ensure_cloud_directory(session, dav_url, dest):
            return {"error": f"Не удалось подготовить директорию {dest}"}

        for f_path, c_name in files_to_process:
            res = upload_xlsx(session, f_path, dest, config, c_name, overwrite)
            results.append(res)

    return results


if __name__ == "__main__":
    # Тестовые данные для проверки модуля
    test_config = {
        "url": "http://localhost",
        "user": "admin",
        "pass": "super_secure_password"
    }
    # Путь к примеру в текущей директории скрипта
    example = os.path.join(os.path.dirname(__file__), "example_upload.xlsx")

    if os.path.exists(example):
        print(upload_batch(test_config, file_path=example,
                           dest="/Test/", overwrite=False))
    else:
        print(f"Для теста создайте файл {example}")
