import requests
from requests.auth import HTTPBasicAuth


OCS_USERS_ENDPOINT = "/ocs/v1.php/cloud/users"


def get_nextcloud_users(base_url, admin_user, admin_pass):
    url = base_url.rstrip("/") + OCS_USERS_ENDPOINT
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }
    
    response = requests.get(url, headers=headers, auth=HTTPBasicAuth(admin_user, admin_pass))
    response.raise_for_status()
    data = response.json()
    users = data.get("ocs", {}).get("data", {}).get("users", [])

    return users
