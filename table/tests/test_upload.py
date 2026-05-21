import uuid

def test_upload_single_file(cli, fixtures_dir):
    file_path = fixtures_dir / "sample.xlsx"
    dest_path = f"/UploadTest_{uuid.uuid4().hex[:8]}"
    
    res = cli("upload", "--file", str(file_path), "--dest", dest_path)
    print(res)
    assert res[0].get("status") == "completed"
