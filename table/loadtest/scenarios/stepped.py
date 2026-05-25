"""
Профиль stepped: 50 -> 100 -> 200 -> 300 одновременных юзеров за 10 минут.
PROPFIND на личную WebDAV-папку юзера + OCS user-status.

Тестовые юзеры должны существовать (см. table/loadtest/users.csv).

Env-override: LOADTEST_USER_PREFIX, LOADTEST_USER_MAX, LOADTEST_PASSWORD.
"""
import os
import random

from locust import HttpUser, task, between, LoadTestShape
from requests.auth import HTTPBasicAuth


USER_PREFIX = os.environ.get("LOADTEST_USER_PREFIX", "s")
USER_MAX = int(os.environ.get("LOADTEST_USER_MAX", "350"))
USER_PASSWORD = os.environ.get("LOADTEST_PASSWORD", "Leti2026!!")


class SteppedUser(HttpUser):
    wait_time = between(1.0, 5.0)

    def on_start(self):
        user_id = random.randint(1, USER_MAX)
        self.username = f"{USER_PREFIX}{user_id:03d}"
        self.auth = HTTPBasicAuth(self.username, USER_PASSWORD)
        self.dav_path = f"/remote.php/dav/files/{self.username}/"

    @task(3)
    def read_files_list(self):
        with self.client.request(
            "PROPFIND",
            self.dav_path,
            auth=self.auth,
            headers={"Depth": "1"},
            name="PROPFIND /dav/files/",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 207):
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def get_user_status(self):
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
        elapsed = 0
        for stage in self.stages:
            elapsed += stage["duration"]
            if run_time < elapsed:
                return stage["users"], stage["spawn_rate"]
        return None
