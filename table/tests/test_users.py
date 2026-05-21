import uuid

def test_user_lifecycle(cli):
	# Создание, поиск, удаление пользователя
    uid = uuid.uuid4().hex[:6]
    username = f"test_user_{uid}"

    # Create
    create_res = cli(
        "users", "create", username,
        "--display-name", f"Pytest {uid}",
        "--email", f"{username}@test.local"
    )
    assert create_res.get("status") == "created"	

    # Проверка наличия пользователя
    list_res = cli("users", "list", "--filter", "username", "exact", username)
    assert isinstance(list_res, dict)
    assert username in str(list_res)
    
    # Delete
    delete_res = cli("users", "delete", username)
    assert delete_res.get("status") == "deleted"
    assert isinstance(delete_res, dict)


def test_users_csv_lifecycle(cli, fixtures_dir):
    # Создание и удаление пользователей из .csv
    csv_file = fixtures_dir / "smoke_users.csv"
    
    try:
        cli("users", "csv-delete", str(csv_file))
    except Exception:
        pass
    
    # Создание пользователей
    users_count_before = len(cli("users", "list").get("users"))
    create_res = cli("users", "csv-create", str(csv_file))
    users_count = len(cli("users", "list").get("users")) - users_count_before
    
    assert create_res.get("total") == users_count
    assert len(create_res.get("failed")) == 0
    assert isinstance(create_res, dict)
    
    # Удаление пользователей
    delete_res = cli("users", "csv-delete", str(csv_file))
    assert delete_res.get("total") == users_count
    assert isinstance(delete_res, dict)
