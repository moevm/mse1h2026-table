import requests

TOKEN = ''  # API-token админа
SEAFILE_URL = ''  # Ссылка на сервис


def list_users(page=1, per_page=50):
    headers = {
        "Authorization": f"Token {TOKEN}",
        "Accept": "application/json"
    }

    url = f"{SEAFILE_URL}/api/v2.1/admin/users/"
    params = {
        "page": page,
        "per_page": per_page
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        print(f"Всего пользователей на странице: {len(data['data'])}")

        for user in data['data']:
            print(f"{user['email']} | Имя: {user.get('name', '—')} | "
                  f"Активен: {user['is_active']} | "
                  f"Лимит: {user['quota_total']} МБ")
        return data
    else:
        print(f"Ошибка {response.status_code}: {response.text}")
        return None


if __name__ == "__main__":
    # Получаем первую страницу пользователей
    list_users(page=1, per_page=50)
