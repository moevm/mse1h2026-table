import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
MANAGE_PY = TESTS_DIR.parent / "manage.py"
 

@pytest.fixture(scope="session", autouse=True)
def setup_stack():
    
    # deploy up
    up_cmd = [sys.executable, str(MANAGE_PY), "deploy", "up"]
    up_res = subprocess.run(up_cmd, capture_output=True, text=True)
    if up_res.returncode != 0:
        pytest.fail(f"Failed to start stack (deploy up):\n{up_res.stderr}")

    # Ожидание готовности
    status_cmd = [
        sys.executable, str(MANAGE_PY), "deploy", "status", 
        "--wait", "--timeout", "300"
    ]
    status_res = subprocess.run(status_cmd, capture_output=True, text=True)
    if status_res.returncode != 0:
        pytest.fail(f"Stack is not ready:\n{status_res.stderr}")

    yield  # Переход к выполнению тестов

    # deploy down
    down_cmd = [sys.executable, str(MANAGE_PY), "deploy", "down"]
    subprocess.run(down_cmd, capture_output=True, text=True)


@pytest.fixture
def cli():
    """
    Контракт хелпера: вызывает manage.py с --output json. 
    Если exit != 0 — pytest.fail с stderr.
    """
    def _cli(*args) -> dict:
        cmd = [sys.executable, str(MANAGE_PY), "--output", "json"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            pytest.fail(
                f"Command '{' '.join(args)}' failed with exit code {result.returncode}.\n"
                f"STDERR: {result.stderr}\n"
                f"STDOUT: {result.stdout}"
            )
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(
                f"Failed to parse JSON.\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )
            
    return _cli


@pytest.fixture(scope="session")
def fixtures_dir():
    """
    Возвращает путь к фикстурам и проверяет наличие 
    необходимых файлов.
    """
    if not FIXTURES_DIR.exists():
        pytest.fail(f"Directory {FIXTURES_DIR} not found. Please create it manually.")
        
    required_files = ["sample.xlsx", "smoke_users.csv", "smoke_import.csv"]
    for file_name in required_files:
        file_path = FIXTURES_DIR / file_name
        if not file_path.exists():
            pytest.fail(
                f"Fixture file '{file_name}' not found in {FIXTURES_DIR}. "
                "Please create it manually before running tests."
            )
            
    return FIXTURES_DIR
    
@pytest.fixture
def cleanup_tasks():
    """
    Фикстура для гарантированной очистки ресурсов после теста.
    Тест добавляет в нее функции, которые нужно вызвать в конце.
    """
    tasks = []
    
    yield tasks  # Отдаем список тесту
    
    # Этот код выполнится ПОСЛЕ завершения теста (успешного или нет)
    for task_func, args in reversed(tasks):
        try:
            task_func(*args)
        except Exception as e:
            print(f"Ошибка при очистке (игнорируется): {e}")
