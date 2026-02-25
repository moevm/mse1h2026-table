import io
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

SEAFILE_URL = ''  # Ссылка на сервис
TOKEN = ''  # API-token пользователя
REPO_ID = ''  # API библиотеки
FILENAME = 'interactive_form.pdf'  # Имя файла на сервере


def get_font_name():
    font_path = (
        "/usr/share/fonts/truetype/liberation/"
        "LiberationSans-Regular.ttf"
    )
    try:
        pdfmetrics.registerFont(TTFont('Arial', font_path))
        print("Шрифт Arial успешно загружен")
        return 'Arial'
    except Exception as e:
        print(f"Не удалось загрузить LiberationSans: {e}. "
              "Используется Helvetica (русский текст не будет отображаться)")
        return 'Helvetica'


def create_interactive_pdf():
    # Создание формы
    print(f"Создание формы: {FILENAME}...")

    font_name = get_font_name()
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    c.setFont(font_name, 14)
    c.drawString(50, 800, "Анкета обратной связи")

    c.setFont(font_name, 10)
    c.drawString(50, 770, "Пожалуйста, введите ваше имя в поле ниже:")

    # Создание интерактивного текстового поля
    form = c.acroForm
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

    c.showPage()
    c.save()

    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


def upload_to_seafile(pdf_data, seafile_url, token, repo_id, filename):
    headers = {"Authorization": f"Token {token}"}

    # Получаем ссылку для загрузки
    upload_link_url = f"{seafile_url}/api2/repos/{repo_id}/upload-link/"
    resp = requests.get(upload_link_url, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Ошибка загрузки: {resp.status_code} - {resp.text}")
    upload_link = resp.json()

    # Загружаем файл
    files = {
        'file': (filename, pdf_data, 'application/pdf')
    }
    data = {
        'filename': filename
    }
    response = requests.post(upload_link, headers=headers,
                             files=files, data=data)
    if response.status_code == 200:
        print(f"Файл успешно загружен в /{filename}")
    else:
        print(f"Ошибка загрузки: {response.status_code} - {response.text}")


def main():
    try:
        pdf_data = create_interactive_pdf()
        upload_to_seafile(pdf_data, SEAFILE_URL, TOKEN, REPO_ID, FILENAME)
    except Exception as e:
        print(f"Ошибка: {e}")


if __name__ == "__main__":
    main()
