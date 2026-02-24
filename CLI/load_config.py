import os
import yaml
import argparse

from yaml import YAMLError


def raise_field_error(text):
    raise ValueError(f'Поле "{text}" пусто')

def load_config(cfg_path):
    # Проверки при открытии файла
    if not cfg_path:
        raise FileExistsError("Ошибка: Не введён путь до конфиг файла")

    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Ошибка: Файл по пути {cfg_path} не найден")
    try:
        with open(cfg_path, "r") as f:
            data = yaml.safe_load(f)
    except YAMLError:
        raise YAMLError("Ошибка: Неккоректный yaml-файл")

    # Проверки на корректность аргументов файла конфигурации
    try:
        if not data['environment']:
            raise_field_error("environment")

        if not data['services']:
            raise_field_error("services")
        else:
            if not isinstance(data['services'], dict):
                raise ValueError('Ошибка: Поле "services" должно быть словарём')
            if not data['services']['table_url']:
                raise_field_error("table_url")
            if not data['services']['form_url']:
                raise_field_error("form_url")

        if not data['backup']:
            raise_field_error("backup")
        else:
            if not isinstance(data['services'], dict):
                raise ValueError('Ошибка: Поле "services" должно быть словарём')
            if not data['backup']['directory']:
                raise_field_error("directory")
    except KeyError as e:
        raise KeyError(f"Ошибка: В файле нет поля {e.args[0]}") from None

    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        help= "Путь до конфиг файла",
        required = True
    )

    args = parser.parse_args()
    cfg_data = load_config(args.config)

    # Вывод конфига
    print(f"Environmnet: {cfg_data['environment']}")
    print(f"Services:\n    table_url{cfg_data['services']['table_url']}\n    form_url{cfg_data['services']['form_url']}")
    print(f"Backup:\n    directory{cfg_data['backup']['directory']}")

if __name__ == "__main__":
    main()