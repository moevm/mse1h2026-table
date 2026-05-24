pip install -r requirements.txt в /locust, чтобы поднять зависимости
тест:
locust -f scenarios/single_request.py --host=https://httpbin.org