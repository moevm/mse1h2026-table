import requests
import openpyxl
import io
from requests.auth import HTTPBasicAuth

# Конфиг !!! НУЖНО ПОПРАВИТЬ ДЛЯ ЗАПУСКА !!!
USER = "admin"  # Ваш логин (ID)
# пример: xxxx-xxxx-xxxx-xxxx
PASS = "" # !!! НУЖНО СГЕНЕРИРОВАТЬ ПАРОЛЬ И ВСТАВИТЬ ЕГО ДЛЯ РАБОТЫ, ТАКЖЕ МОЖЕТ НЕ РАБОТАТЬ В ОНЛАЙНЕ, ЛОКАЛЬНО РАБОТАЕТ !!!
FILENAME = "table.xlsx"
BASE_URL = f"http://localhost/remote.php/dav/files/{USER}/{FILENAME}"
auth = HTTPBasicAuth(USER, PASS)

def write_to_table():
    # Пытаемся скачать существующий файл
    resp = requests.get(BASE_URL, auth=auth)
    
    if resp.status_code == 200:
        # Файл найден
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        sheet = wb.active
    else:
        # Файла нет - создаем новый
        print("Файл не найден на сервере, создаю новый...")
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.append(["Дата", "Параметр", "Значение"]) # Заголовки

    # Добавляем данные
    sheet.append(["2023-10-27", "Тест из Python", "ОК"])

    # Загружаем на сервер
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    put_resp = requests.put(BASE_URL, data=output, auth=auth)
    
    if put_resp.status_code in [201, 204]:
        print(f"Успешно записано в {FILENAME}")
    else:
        print(f"Ошибка сохранения: {put_resp.status_code}")

if __name__ == "__main__":
    write_to_table()