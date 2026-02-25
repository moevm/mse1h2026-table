import requests
from requests.auth import HTTPBasicAuth

# Конфиг !!! НУЖНО ИСПОЛЬЗОВАТЬ ЛОГИН/ПАРОЛЬ АДМИНИСТРАТОРА !!!
ADMIN_USER = "admin"
# пример: xxxx-xxxx-xxxx-xxxx
ADMIN_PASS = ""  # !!! НУЖНО СГЕНЕРИРОВАТЬ ПАРОЛЬ И ВСТАВИТЬ ЕГО ДЛЯ РАБОТЫ,
# ТАКЖЕ МОЖЕТ НЕ РАБОТАТЬ В ОНЛАЙНЕ, ЛОКАЛЬНО РАБОТАЕТ !!!

# Данные нового пользователя
NEW_USER_ID = "ivan_ivanov"
NEW_USER_PASS = "hfosjrnvoiisjls"
NEW_USER_DISPLAYNAME = "Иван Иванов"
NEW_USER_EMAIL = "ivan@example.com"

# Путь к API создания пользователей
API_URL = "http://localhost/ocs/v1.php/cloud/users"
auth = HTTPBasicAuth(ADMIN_USER, ADMIN_PASS)

# Заголовок OCS-APIRequest
HEADERS = {
    "OCS-APIRequest": "true",
    "Content-Type": "application/x-www-form-urlencoded"
}


def create_nextcloud_user():
    print(f"Попытка создания пользователя: {NEW_USER_ID}...")

    # Данные запроса
    payload = {
        "userid": NEW_USER_ID,
        "password": NEW_USER_PASS,
        "displayName": NEW_USER_DISPLAYNAME,
        "email": NEW_USER_EMAIL
    }

    # Отправляем POST запрос
    # format=json, чтобы получить ответ в формате JSON вместо XML
    resp = requests.post(f"{API_URL}?format=json", data=payload, auth=auth,
                         headers=HEADERS)

    if resp.status_code == 200:
        data = resp.json()
        status_code = data['ocs']['meta']['statuscode']

        if status_code == 100:
            print(f"Успех! Пользователь '{NEW_USER_ID}' создан.")
        elif status_code == 102:
            print("Ошибка: Такой пользователь уже существует.")
        else:
            message = data['ocs']['meta']['message']
            print(f"Ошибка API (код {status_code}): {message}")
    else:
        print(f"Ошибка соединения: {resp.status_code}")
        print(resp.text)


if __name__ == "__main__":
    create_nextcloud_user()
