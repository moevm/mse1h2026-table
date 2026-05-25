"""
Тот же набор запросов что в stepped.py, но без LoadTestShape — управляется
флагами --users / --spawn-rate / --run-time.
"""
import os
import random

from locust import HttpUser, task, between
from requests.auth import HTTPBasicAuth


USER_PREFIX = os.environ.get("LOADTEST_USER_PREFIX", "s")
USER_MAX = int(os.environ.get("LOADTEST_USER_MAX", "350"))
USER_PASSWORD = os.environ.get("LOADTEST_PASSWORD", "Leti2026!!")


class SmokeUser(HttpUser):
    wait_time = between(1.0, 3.0)

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
