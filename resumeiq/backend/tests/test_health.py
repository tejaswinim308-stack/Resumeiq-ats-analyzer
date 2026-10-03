def test_health_endpoint_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["status"] == "ok"
    assert "gemini_configured" in data
    assert "firebase_configured" in data


def test_analyze_missing_job_description_returns_validation_error(client, minimal_pdf_file):
    stream, filename = minimal_pdf_file
    resp = client.post(
        "/api/analyze",
        data={"resume": (stream, filename)},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "missing_job_description"


def test_analyze_invalid_pdf_returns_validation_error(client):
    import io

    bad_file = (io.BytesIO(b"not a real pdf"), "resume.pdf")
    resp = client.post(
        "/api/analyze",
        data={"resume": bad_file, "job_description": "We need a backend engineer with 5 years of Python experience."},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["success"] is False
    assert data["error"]["code"] == "invalid_file"


def test_unknown_route_returns_clean_404(client):
    resp = client.get("/api/does-not-exist")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["success"] is False
