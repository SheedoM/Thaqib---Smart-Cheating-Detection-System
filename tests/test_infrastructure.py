def test_create_institution_as_admin(client, admin_token_headers):
    data = {"name": "Test Inst", "code": "TST"}
    response = client.post("/api/institutions/", json=data, headers=admin_token_headers)
    assert response.status_code == 201
    assert response.json()["code"] == "TST"

def test_create_institution_as_invigilator(client, invigilator_token_headers):
    data = {"name": "Test Inst", "code": "TST"}
    response = client.post("/api/institutions/", json=data, headers=invigilator_token_headers)
    assert response.status_code == 403
    assert "roles: ['admin']" in response.json()["detail"]

def test_create_hall_as_admin(client, admin_token_headers, test_institution):
    data = {"name": "Hall A", "capacity": 50}
    response = client.post(f"/api/halls/?institution_id={test_institution.id}", json=data, headers=admin_token_headers)
    assert response.status_code == 201
    assert response.json()["name"] == "Hall A"

def test_create_hall_as_invigilator(client, invigilator_token_headers, test_institution):
    data = {"name": "Hall B", "capacity": 30}
    response = client.post(f"/api/halls/?institution_id={test_institution.id}", json=data, headers=invigilator_token_headers)
    assert response.status_code == 403
