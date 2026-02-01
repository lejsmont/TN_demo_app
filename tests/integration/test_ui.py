
def test_index_renders_tabs(client, tmp_path):
    client.application.config["DATA_DIR"] = tmp_path
    response = client.get("/")
    assert response.status_code == 200
    body = response.data.decode("utf-8")
    assert "Transaction Notifications Demo Console" in body
    assert "Enroll via API" in body
    assert "Hosted Consent UI" in body
    assert "Test cards (sandbox)" in body
    assert "Post a transaction" in body
    assert "Dashboard" in body
    assert "No enrollments yet" in body
