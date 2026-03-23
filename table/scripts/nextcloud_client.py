import requests


REQUEST_TIMEOUT = 30


class NextcloudClient:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            "OCS-APIRequest": "true",
            "Accept": "application/json"
        })

    def get_users(self):
        url = f"{self.base_url}/ocs/v1.php/cloud/users"
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        return resp.json()["ocs"]["data"]["users"]

    def get_user_details(self, username):
        url = f"{self.base_url}/ocs/v1.php/cloud/users/{username}"
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)

        resp.raise_for_status()
        data = resp.json()["ocs"]["data"]

        return {
            "username": data.get("id"),
            "email": data.get("email"),
            "groups": data.get("groups", []),
            "quota": data.get("quota", {}),
        }

    def create_user(
        self, userid, password=None, email=None,
        displayName=None, quota=None, groups=None
    ):

        url = f"{self.base_url}/ocs/v1.php/cloud/users"
        payload = {"userid": userid}
        if password is not None:
            payload["password"] = password
        if email is not None:
            payload["email"] = email
        if displayName is not None:
            payload["displayName"] = displayName
        if quota is not None:
            payload["quota"] = quota
        if groups is not None:
            payload["groups[]"] = groups

        resp = self.session.post(url, data=payload, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        ocs = resp.json()["ocs"]["meta"]
        if ocs["statuscode"] != 100:
            raise Exception(f"{ocs['statuscode']}: {ocs['message']}")

    def delete_user(self, username):
        url = f"{self.base_url}/ocs/v1.php/cloud/users/{username}"
        resp = self.session.delete(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        ocs = resp.json()["ocs"]["meta"]
        if ocs["statuscode"] != 100:
            raise Exception(f"{ocs['statuscode']}: {ocs['message']}")
