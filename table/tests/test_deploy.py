def test_deploy_status(cli):
    res = cli("deploy", "status")
    
    # общий статус системы
    assert res.get("overall") == "ok"
    
    # компонент Nextcloud (приложение установилось и отвечает 200 OK)
    nextcloud_info = res.get("components", {}).get("nextcloud", {})
    assert nextcloud_info.get("status") == "ok"
    assert nextcloud_info.get("installed") is True
    assert nextcloud_info.get("maintenance") is False
    assert nextcloud_info.get("http_code") == 200

    # состояние контейнеров (например, что app и db healthy)
    containers = res.get("components", {}).get("containers", {}).get("items", {})
    
    # контейнер app (PHP/Nextcloud)
    app_container = containers.get("app", {})
    assert app_container.get("state") == "running"
    assert app_container.get("health") == "healthy"

    # контейнер db (PostgreSQL)
    db_container = containers.get("db", {})
    assert db_container.get("state") == "running"
    assert db_container.get("health") == "healthy"
