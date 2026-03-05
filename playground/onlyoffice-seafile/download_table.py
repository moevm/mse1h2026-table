import requests

TOKEN = ''  # API-token пользователя
SEAFILE_URL = ''  # Ссылка на сервис
REPO_ID = ''  # API библиотеки
PATH = '/test.xlsx'  # Путь до скачиваемого файла
LOCAL_PATH = 'download_test.xlsx'  # Имя файла после скачивания


def download_file(token, seafile_url, repo_id, path, local_path):
    headers = {"Authorization": f"Token {token}"}

    # Получение ссылки на скачивание
    api_url = f"{seafile_url}/api2/repos/{repo_id}/file/?p={path}"
    response = requests.get(api_url, headers=headers)

    if response.status_code != 200:
        print(f"Ошибка получения ссылки: {response.status_code}")
        return

    download_link = response.json()

    # Скачивание файла по полученной ссылке
    file_response = requests.get(download_link, headers=headers)

    if file_response.status_code == 200:
        with open(local_path, "wb") as f:
            f.write(file_response.content)
        print(f"Файл успешно скачан и сохранен как '{local_path}'")
    else:
        print(f"Ошибка скачивания файла: {file_response.status_code}")


if __name__ == "__main__":
    download_file(TOKEN, SEAFILE_URL, REPO_ID, PATH, LOCAL_PATH)
