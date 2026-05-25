from locust import HttpUser, task, between, LoadTestShape


class SteppedUser(HttpUser):
    wait_time = between(0.5, 1.5)

    @task(3)
    def read(self):
        with self.client.get(
            "/get",
            params={"step": "load_shape"},
            name="GET /get",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def write(self):
        with self.client.post(
            "/post",
            json={"event": "user_action", "ts": __import__("time").time()},
            name="POST /post",
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
