import requests

SEAFILE_URL = ''  # Ссылка на сервис
ADMIN_TOKEN = ''  # API-токен администратора
NEW_USER_EMAIL = ''  # Email нового пользователя
NEW_USER_PASSWORD = ''  # Пароль нового пользователя


def create_user(seafile_url, admin_token, email, password):
    headers = {"Authorization": f"Token {admin_token}"}

    # Данные нового пользователя
    data = {
        "password": password,
        "is_staff": "false",  # false = обычный пользователь
        "is_active": "true"  # Сразу активирован
    }

    # URL для создания пользователя
    url = f"{seafile_url}/api/v2.1/admin/users/{email}/"
    response = requests.put(url, headers=headers, data=data)

    if response.status_code == 201:
        print(f"Пользователь {email} успешно создан")
    else:
        print(f"Ошибка создания пользователя: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    create_user(SEAFILE_URL, ADMIN_TOKEN, NEW_USER_EMAIL, NEW_USER_PASSWORD)
