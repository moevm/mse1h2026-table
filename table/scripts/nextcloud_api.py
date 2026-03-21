import requests
from requests.auth import HTTPBasicAuth


OCS_USERS_ENDPOINT = "/ocs/v1.php/cloud/users"


def get_nextcloud_users(base_url, admin_user, admin_pass):
    url = base_url.rstrip("/") + OCS_USERS_ENDPOINT
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }

    response = requests.get(
        url, headers=headers, auth=HTTPBasicAuth(admin_user, admin_pass)
    )
    response.raise_for_status()

    data = response.json()
    users = data.get("ocs", {}).get("data", {}).get("users", [])

    return users


def get_nextcloud_user_details(base_url, admin_user, admin_pass, username):
    url = base_url.rstrip("/") + OCS_USERS_ENDPOINT + f"/{username}"
    headers = {
        "OCS-APIRequest": "true",
        "Accept": "application/json"
    }

    response = requests.get(
        url, headers=headers, auth=HTTPBasicAuth(admin_user, admin_pass)
    )
    response.raise_for_status()

    data = response.json()
    user_data = data.get("ocs", {}).get("data", {})

    return {
        "username": user_data.get("id"),
        "email": user_data.get("email"),
        "groups": user_data.get("groups", []),
        "quota": user_data.get("quota", {}),
    }
