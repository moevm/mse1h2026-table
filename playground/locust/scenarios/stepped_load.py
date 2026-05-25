import random
from locust import HttpUser, task, between, LoadTestShape
from requests.auth import HTTPBasicAuth


class SteppedUser(HttpUser):
    # Пауза между действиями юзера (имитация чтения)
    wait_time = between(1.0, 5.0)

    def on_start(self):
        # В CSV студенты имеют логины от s001 до s350
        user_id = random.randint(1, 350)
        self.username = f"s{user_id:03d}"
        self.password = "Leti2026!!"
        self.auth = HTTPBasicAuth(self.username, self.password)

        self.dav_path = f"/remote.php/dav/files/{self.username}/"

    @task(3)
    def read_files_list(self):
        # Имитация открытия папки (WebDAV PROPFIND)
        with self.client.request(
            "PROPFIND",
            self.dav_path,
            auth=self.auth,
            headers={"Depth": "1"},
            name="PROPFIND /dav/files/",
            catch_response=True,
        ) as resp:
            if resp.status_code in [200, 207]:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def get_user_status(self):
        # Имитация фонового запроса клиента Nextcloud
        with self.client.get(
            "/ocs/v2.php/cloud/user?format=json",
            auth=self.auth,
            headers={"OCS-APIRequest": "true"},
            name="GET /ocs/v2/user",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")


class StepLoadShape(LoadTestShape):
    stages = [
        {"duration": 60,  "users": 50,  "spawn_rate": 10},
        {"duration": 120, "users": 100, "spawn_rate": 10},
        {"duration": 180, "users": 200, "spawn_rate": 20},
        {"duration": 240, "users": 300, "spawn_rate": 20},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None
