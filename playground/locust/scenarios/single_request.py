from locust import HttpUser, task, between


class SingleRequestUser(HttpUser):
    # пауза 1-3 секунды между запросами
    wait_time = between(1, 3)

    @task
    def get_anything(self):
        with self.client.get(
            "/get",
            params={"source": "locust", "scenario": "single"},
            name="GET /get",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("args", {}).get("source") != "locust":
                    resp.failure("Unexpected response body")
                else:
                    resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")
