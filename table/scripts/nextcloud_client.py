import requests


REQUEST_TIMEOUT = 30


def _parse_ocs(resp):
    """
    Распарсить ответ OCS API: проверить HTTP, вытащить meta.statuscode.

    Возвращает блок ocs.data при statuscode == 100.
    Бросает Exception с сообщением OCS при остальных кодах
    (включая 997 — auth fail).
    """
    resp.raise_for_status()
    try:
        ocs = resp.json()["ocs"]
    except (ValueError, KeyError) as e:
        raise Exception(f"Некорректный OCS-ответ: {e}")

    meta = ocs.get("meta", {})
    code = meta.get("statuscode")
    if code != 100:
        message = meta.get("message") or "<no message>"
        raise Exception(f"{code}: {message}")
    return ocs.get("data", {})


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
        return _parse_ocs(resp).get("users", [])

    def get_user_details(self, username):
        url = f"{self.base_url}/ocs/v1.php/cloud/users/{username}"
        resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
        data = _parse_ocs(resp)

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
        _parse_ocs(resp)

    def delete_user(self, username):
        url = f"{self.base_url}/ocs/v1.php/cloud/users/{username}"
        resp = self.session.delete(url, timeout=REQUEST_TIMEOUT)
        _parse_ocs(resp)
