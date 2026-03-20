import csv
import os
import requests
import logging

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


def _ensure_group_exists(session, api_base_url, group_name):
    """
    Проверяет наличие группы в Nextcloud и создает её, если она отсутствует.

    Использует переданную сессию для выполнения запроса. Это вспомогательная
    функция, позволяющая избежать ошибки при добавлении пользователя
    в несуществующую группу.

    Args:
        session (requests.Session): Активная HTTP-сессия с авторизацией.
        api_base_url (str): Базовый URL API (без /ocs/v1.php...).
        group_name (str): Название группы.

    Returns:
        tuple: (success (bool), created_new (bool))
            - success: True, если группа существует или была успешно создана.
            - created_new: True, если группа была создана только что.
    """
    if not group_name:
        return False, False

    # Формируем URL для работы с группами
    url = f"{api_base_url.rstrip('/')}/ocs/v1.php/cloud/groups"

    try:
        payload = {"groupid": group_name}
        # Параметр format=json обязателен для удобного парсинга
        resp = session.post(f"{url}?format=json", data=payload,
                            timeout=REQUEST_TIMEOUT)

        if resp.status_code == 200:
            data = resp.json()
            meta = data.get('ocs', {}).get('meta', {})
            code = meta.get('statuscode')

            # 100 = OK (Группа создана)
            if code == 100:
                return True, True
            # 101/102 = Группа уже существует (не считается ошибкой)
            if code in [101, 102]:
                return True, False

            logger.warning(
                f"API message creating group '{group_name}': {meta.get('message')}")
            return False, False

    except Exception as e:
        logger.error(f"Error checking group '{group_name}': {e}")
        return False, False

    return True, False


def create_users_from_csv(csv_path, api_base_url, admin_user, admin_pass):
    """
    Массовое создание пользователей Nextcloud на основе CSV файла.

    Особенности реализации:
    1. Использует requests.Session для Keep-Alive соединений (ускорение).
    2. Автоматически создает отсутствующие группы.
    3. Корректно обрабатывает массивы групп (syntax `groups[]`).
    4. Поддерживает установку квот и администраторов групп.

    Args:
        csv_path (str): Путь к CSV файлу с данными пользователей.
        api_base_url (str): URL Nextcloud (например, http://localhost:8080).
        admin_user (str): Логин администратора.
        admin_pass (str): Пароль администратора.

    Returns:
        dict: Отчет о выполнении следующего формата:
            {
                "total": int,
                "created": [list of user_ids],
                "failed": [list of error dicts],
                "groups_created": [list of group_names]
            }
    """
    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    # Endpoint создания пользователей
    users_url = (
        f"{api_base_url.rstrip('/')}/ocs/v1.php/cloud/users?format=json"
    )

    headers = {
        "OCS-APIRequest": "true",  # Обязательный заголовок для OCS API
        "Content-Type": "application/x-www-form-urlencoded"
    }

    report = {
        "total": 0,
        "created": [],
        "failed": [],
        "groups_created": []
    }

    # Кеш проверенных групп, чтобы не спамить API запросами на проверку
    # одной и той же группы для каждого пользователя.
    checked_groups = set()

    # Открываем сессию (Context Manager закрывает соединение автоматически)
    with requests.Session() as session:
        session.auth = (admin_user, admin_pass)
        session.headers.update(headers)

        try:
            with open(csv_path, mode='r', encoding='utf-8') as csvfile:
                # Пытаемся автоматически определить разделитель (',' или ';')
                try:
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    # Если файл слишком мал или сложен, используем Excel
                    dialect = 'excel'

                reader = csv.DictReader(csvfile, dialect=dialect)

                # Нормализуем заголовки (нижний регистр, без пробелов)
                # для устойчивости к человеческим ошибкам в CSV
                field_map = {
                    f.lower().strip(): f for f in (reader.fieldnames or [])
                }

                # Проверка обязательных полей
                if 'login' not in field_map or 'password' not in field_map:
                    return {
                        "error": "CSV must contain 'login' and 'password' cols"
                    }

                for row in reader:
                    report['total'] += 1

                    user_id = row.get(field_map['login'], '').strip()
                    password = row.get(field_map['password'], '').strip()

                    if not user_id or not password:
                        report['failed'].append({
                            "user": "UNKNOWN",
                            "reason": "Missing login or password"
                        })
                        continue

                    # --- ЭТАП 1: Подготовка групп ---
                    # Собираем все группы, куда нужно добавить пользователя
                    # или назначить админом
                    all_groups = []

                    # 1. Группы участия
                    groups_val = row.get(field_map.get('groups'), '')
                    if groups_val:
                        g_list = [
                            g.strip() for g in groups_val.split(',')
                            if g.strip()
                        ]
                        all_groups.extend(g_list)

                    # 2. Группы администрирования (Subadmin)
                    sub_val = row.get(field_map.get('subadmin_groups'), '')
                    if sub_val:
                        s_list = [
                            s.strip() for s in sub_val.split(',')
                            if s.strip()
                        ]
                        all_groups.extend(s_list)

                    # Проверяем существование групп перед созданием юзера
                    for g in set(all_groups):
                        if g and g not in checked_groups:
                            success, created = _ensure_group_exists(
                                session, api_base_url, g
                            )
                            if success:
                                checked_groups.add(g)
                                if created:
                                    report['groups_created'].append(g)

                    # --- ЭТАП 2: Формирование тела запроса (Payload) ---
                    payload = {
                        "userid": user_id,
                        "password": password
                    }

                    if 'email' in field_map and row.get(field_map['email']):
                        payload['email'] = row[field_map['email']].strip()

                    if 'display_name' in field_map and \
                            row.get(field_map['display_name']):
                        val = row[field_map['display_name']].strip()
                        payload['displayName'] = val

                    # Обработка квоты
                    if 'quota' in field_map and row.get(field_map['quota']):
                        q = row[field_map['quota']].strip()
                        # Nextcloud API принимает 'none' для безлимита
                        payload['quota'] = ('none' if q.lower() ==
                                            'unlimited' else q)

                    # ВАЖНО: PHP API требует ключи с '[]' для массивов
                    if groups_val:
                        payload['groups[]'] = [
                            g.strip() for g in
                            groups_val.split(',') if g.strip()
                        ]

                    if sub_val:
                        payload['subadmin[]'] = [
                            s.strip() for s in
                            sub_val.split(',') if s.strip()
                        ]

                    # Поле 'manager'  из csv файла игнорируем при отправке,
                    # так как
                    # стандартный API Nextcloud его не поддерживает.

                    # --- ЭТАП 3: Отправка запроса ---
                    try:
                        resp = session.post(users_url, data=payload,
                                            timeout=REQUEST_TIMEOUT)

                        if resp.status_code == 200:
                            try:
                                data = resp.json()
                                meta = data.get('ocs', {}).get('meta', {})
                                code = meta.get('statuscode')
                                msg = meta.get('message')

                                if code == 100:
                                    report['created'].append(user_id)
                                else:
                                    # Ошибки уровня API
                                    # например, слабый пароль
                                    report['failed'].append({
                                        "user": user_id,
                                        "code": code,
                                        "reason": msg
                                    })
                            except ValueError:
                                report['failed'].append({
                                    "user": user_id,
                                    "reason":
                                    "Invalid JSON response from server"
                                })
                        else:
                            # Ошибки HTTP (4xx, 5xx)
                            report['failed'].append({
                                "user": user_id,
                                "http_code": resp.status_code,
                                "reason": resp.text[:200]
                            })

                    except requests.RequestException as e:
                        report['failed'].append({
                            "user": user_id,
                            "reason": f"Network Error: {e}"
                        })

        except Exception as e:
            return {"error": f"Critical script error: {e}"}

    return report


def delete_users_from_csv(csv_path, api_base_url, admin_user, admin_pass):
    """
    Массовое удаление пользователей, перечисленных в CSV файле.
    Полезно для очистки данных после тестирования.

    Args:
        csv_path (str): Путь к CSV файлу (требуется колонка 'login').
        api_base_url (str): URL Nextcloud.
        admin_user (str): Логин администратора.
        admin_pass (str): Пароль администратора.

    Returns:
        dict: Отчет с ключами 'total', 'deleted', 'failed'.
    """
    if not os.path.exists(csv_path):
        return {"error": f"File not found: {csv_path}"}

    headers = {"OCS-APIRequest": "true"}

    report = {
        "total": 0,
        "deleted": [],
        "failed": []
    }

    with requests.Session() as session:
        session.auth = (admin_user, admin_pass)
        session.headers.update(headers)

        try:
            with open(csv_path, mode='r', encoding='utf-8') as csvfile:
                # Определение диалекта CSV
                try:
                    sample = csvfile.read(1024)
                    csvfile.seek(0)
                    dialect = csv.Sniffer().sniff(sample)
                except csv.Error:
                    dialect = 'excel'

                reader = csv.DictReader(csvfile, dialect=dialect)
                field_map = {
                    f.lower().strip(): f for f in (reader.fieldnames or [])
                }

                if 'login' not in field_map:
                    return {
                        "error": "CSV must contain a 'login' column for delete"
                    }

                for row in reader:
                    report['total'] += 1
                    user_id = row.get(field_map['login'], '').strip()

                    if not user_id:
                        report['failed'].append({
                            "user": "UNKNOWN",
                            "reason": "Missing login in row"
                        })
                        continue

                    # Endpoint для удаления конкретного пользователя
                    delete_url = (
                        f"{api_base_url.rstrip('/')}/ocs/v1.php/cloud/"
                        f"users/{user_id}?format=json"
                    )

                    try:
                        resp = session.delete(delete_url,
                                              timeout=REQUEST_TIMEOUT)

                        if resp.status_code == 200:
                            try:
                                data = resp.json()
                                meta = data.get('ocs', {}).get('meta', {})
                                code = meta.get('statuscode')
                                msg = meta.get('message')

                                if code == 100:
                                    report['deleted'].append(user_id)
                                elif code == 102:
                                    # Код 102 обычно означает "User not found"
                                    # при попытке удаления
                                    report['deleted'].append(
                                        f"{user_id} (not found)"
                                    )
                                else:
                                    report['failed'].append({
                                        "user": user_id,
                                        "code": code,
                                        "reason": msg
                                    })
                            except ValueError:
                                report['failed'].append({
                                    "user": user_id,
                                    "reason": "Invalid JSON response"
                                })
                        else:
                            report['failed'].append({
                                "user": user_id,
                                "http_code": resp.status_code,
                                "reason": resp.text[:200]
                            })

                    except requests.RequestException as e:
                        report['failed'].append({
                            "user": user_id,
                            "reason": f"Network Error: {e}"
                        })

        except Exception as e:
            return {"error": f"Critical script error: {e}"}

    return report


# Функция для тестирования вне CLI
if __name__ == "__main__":
    # print(create_users_from_csv(
    #     "D:/Prog/Labs/OPRPO/mse1h2026-table/table/scripts/users_example.csv",
    #     "http://localhost",
    #     "admin",
    #     "super_secure_password")
    #     )
    print(delete_users_from_csv(
        "D:/Prog/Labs/OPRPO/mse1h2026-table/table/scripts/users_example.csv",
        "http://localhost",
        "admin",
        "super_secure_password")
        )
