import uuid
import time

def test_backup_and_restore_lifecycle(cli):
    # Создание пользователя
    uid = uuid.uuid4().hex[:6]
    test_user = f"backup_user_{uid}"
    backup_name = f"test_backup_{uid}"
    
    cli(
        "users", "create", test_user, 
        "--display-name", f"Pytest {uid}", 
        "--email", f"{test_user}@test.local"
    )
    
    users_before = cli("users", "list", "--filter", "username", "exact", test_user)
    assert test_user in str(users_before), "Пользователь должен существовать до бэкапа"

    # Создание бэкапа
    create_res = cli("backup", "create", "--name", backup_name, "--components", "all")
    assert isinstance(create_res, dict)
    
    list_res = cli("backup", "list")
    backup_id = None
    
    items = list_res.get("backups", list_res) 
    for item in items:
        if item.get("id") == backup_name:
            backup_id = item.get("id")
    print(list_res)
    
    assert backup_id == backup_name

    # Удаление пользователя
    cli("users", "delete", test_user)
    users_deleted = cli("users", "list", "--filter", "username", "exact", test_user)
    assert test_user not in str(users_deleted)

    # Восстановление бэкапа
    restore_res = cli("backup", "restore", backup_id, "--force")
    assert isinstance(restore_res, dict)
    assert restore_res.get("status") != "error", f"Ошибка при восстановлении: {restore_res}"

    time.sleep(2)

    # Проверка восстановления пользователя
    users_after_restore = cli("users", "list", "--filter", "username", "exact", test_user)
    assert test_user in str(users_after_restore), (
        "Пользователь не был восстановлен из бэкапа! "
        "Проверьте, что в компонент 'all' входит дамп базы данных."
    )
