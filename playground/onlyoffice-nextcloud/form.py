import requests
import io
import os
from requests.auth import HTTPBasicAuth
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

# Конфиг !!! НУЖНО ПОПРАВИТЬ ДЛЯ ЗАПУСКА !!!
USER = "admin"
# пример: xxxx-xxxx-xxxx-xxxx
PASS = ""  # !!! НУЖНО СГЕНЕРИРОВАТЬ ПАРОЛЬ И ВСТАВИТЬ ЕГО ДЛЯ РАБОТЫ,
# ТАКЖЕ МОЖЕТ НЕ РАБОТАТЬ В ОНЛАЙНЕ, ЛОКАЛЬНО РАБОТАЕТ !!!
FILENAME = "interactive_form.pdf"
BASE_URL = f"http://localhost/remote.php/dav/files/{USER}/{FILENAME}"
auth = HTTPBasicAuth(USER, PASS)


def create_interactive_pdf():
    print(f"Создание интерактивного PDF: {FILENAME}...")

    # Шрифт Arial для кириллицы
    font_path = "C:/Windows/Fonts/arial.ttf"
    font_name = 'ArialCustom'
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont(font_name, font_path))
    else:
        font_name = 'Helvetica'

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Статический текст
    c.setFont(font_name, 14)
    c.drawString(50, 800, "Анкета обратной связи")

    c.setFont(font_name, 10)
    c.drawString(50, 770, "Пожалуйста, введите ваше имя в поле ниже:")

    # Создание интерактивного текстового поля (AcroForm)
    form = c.acroForm

    # Параметры: имя поля, подсказка, координаты x, y, ширина, высота
    form.textfield(
        name='f_name',
        tooltip='Введите имя',
        x=50, y=730, width=300, height=25,
        borderStyle='inset',
        borderWidth=1,
        borderColor=colors.gray,
        forceBorder=True,
        fontSize=12
    )

    c.drawString(50, 710, "(это поле можно заполнить в OnlyOffice)")

    c.showPage()
    c.save()

    # Отправка в Nextcloud
    buffer.seek(0)
    resp = requests.put(BASE_URL, data=buffer, auth=auth)

    if resp.status_code in [201, 204]:
        print("Успешно! PDF с текстовым полем загружен.")
    else:
        print(f"Ошибка: {resp.status_code}")


if __name__ == "__main__":
    create_interactive_pdf()
