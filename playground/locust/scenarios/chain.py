import uuid
from locust import HttpUser, SequentialTaskSet, task, between


class UserSession(SequentialTaskSet):
    token: str = ""

    @task
    def step1_login(self):
        payload = {"username": "testuser", "password": "secret"}
        with self.client.post(
            "/post",
            json=payload,
            name="POST /post [login]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                sent = body.get("json") or {}
                if sent.get("username") == "testuser":
                    self.token = f"fake-jwt-{uuid.uuid4().hex[:16]}"
                    resp.success()
                else:
                    resp.failure("Login: unexpected body")
            else:
                resp.failure(f"Login HTTP {resp.status_code}")

    @task
    def step2_create_resource(self):
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {"title": "New item", "value": 42}

        with self.client.post(
            "/post",
            json=payload,
            headers=headers,
            name="POST /post [create]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                body = resp.json()
                auth_header = body.get("headers", {}).get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    resp.success()
                else:
                    resp.failure(
                        "Create: Authorization header missing in echo"
                    )
            else:
                resp.failure(f"Create HTTP {resp.status_code}")

    @task
    def step3_read_state(self):
        if not self.token:
            return

        headers = {"Authorization": f"Bearer {self.token}"}

        with self.client.get(
            "/get",
            params={"filter": "active"},
            headers=headers,
            name="GET /get [read]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Read HTTP {resp.status_code}")

        self.token = ""


class ChainUser(HttpUser):
    tasks = [UserSession]
    wait_time = between(1, 2)
