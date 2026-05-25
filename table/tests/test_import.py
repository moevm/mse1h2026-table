import uuid


def test_import_run(cli, fixtures_dir):
    csv_file = fixtures_dir / "smoke_import.csv"
    target_xlsx = f"/ImportTest_{uuid.uuid4().hex[:8]}.xlsx"

    res = cli(
        "import",
        "--csv", str(csv_file),
        "--target", target_xlsx,
        "--key", "key_col",
        "--create-if-missing"
    )

    assert isinstance(res, dict)
