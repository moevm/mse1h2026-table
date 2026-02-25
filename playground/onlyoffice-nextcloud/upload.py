import requests
import io
from requests.auth import HTTPBasicAuth

# Конфиг !!! НУЖНО ПОПРАВИТЬ ДЛЯ ЗАПУСКА !!!
USER = "admin"  # Ваш логин (ID)
# пример: xxxx-xxxx-xxxx-xxxx
PASS = "" # !!! НУЖНО СГЕНЕРИРОВАТЬ ПАРОЛЬ И ВСТАВИТЬ ЕГО ДЛЯ РАБОТЫ, ТАКЖЕ МОЖЕТ НЕ РАБОТАТЬ В ОНЛАЙНЕ, ЛОКАЛЬНО РАБОТАЕТ !!!
FILENAME = "table.xlsx"
BASE_URL = f"http://localhost/remote.php/dav/files/{USER}/{FILENAME}"
auth = HTTPBasicAuth(USER, PASS)

def download_table():
    # Запрашиваем файл с сервера
    print(f"Скачиваю файл {FILENAME}...")
    resp = requests.get(BASE_URL, auth=auth)
    
    if resp.status_code == 200:
        # Файл получен, сохраняем его локально
        with open("downloaded_table.xlsx", "wb") as f:
            f.write(resp.content)
        print("Файл успешно скачан и сохранен как 'downloaded_table.xlsx'")
    elif resp.status_code == 404:
        print("Ошибка: Файл не найден на сервере.")
    else:
        print(f"Ошибка выгрузки: {resp.status_code}")

if __name__ == "__main__":
    download_table()