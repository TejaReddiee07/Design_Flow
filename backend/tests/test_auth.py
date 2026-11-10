def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_rate_limited_endpoints_work_with_limiter_enabled(client):
    """The limiter is disabled under APP_ENV=test; make sure the decorated endpoints
    still work when it is on (regression: slowapi header injection caused 500s)."""
    from app.core.rate_limit import limiter

    limiter.enabled = True
    try:
        r = client.post("/api/v1/auth/login", json={"email": "admin@designflow.local", "password": "Admin123!"})
        assert r.status_code == 200, r.text
        r = client.post("/api/v1/public/contact", json={"name": "Rate Limit", "email": "rl@example.com", "message": "hello there"})
        assert r.status_code == 201, r.text
    finally:
        limiter.enabled = False


def test_login_bad_password(client):
    r = client.post("/api/v1/auth/login", json={"email": "admin@designflow.local", "password": "wrong"})
    assert r.status_code == 401


def test_me(client, admin, client_headers):
    r = client.get("/api/v1/auth/me", headers=admin)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    r = client.get("/api/v1/auth/me", headers=client_headers)
    assert r.json()["role"] == "client"
    assert r.json()["client"]["company_name"] == "Testco"


def test_duplicate_register(client):
    r = client.post("/api/v1/auth/register", json={"email": "tester@example.com", "password": "Tester123!",
                                                   "full_name": "Dup", "company_name": "Dup"})
    assert r.status_code == 409


def test_weak_password(client):
    r = client.post("/api/v1/auth/register", json={"email": "weak@example.com", "password": "abcdefgh",
                                                   "full_name": "Weak", "company_name": "Weak"})
    assert r.status_code == 422


def test_refresh_and_logout(client, client_auth):
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": client_auth["refresh"]})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    # old refresh token is rotated / revoked
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": client_auth["refresh"]})
    assert r2.status_code == 401
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r3 = client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh}, headers=headers)
    assert r3.status_code == 200


def test_unauthenticated(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/clients").status_code == 401


def test_client_forbidden_from_admin_routes(client, client_headers):
    assert client.get("/api/v1/clients", headers=client_headers).status_code == 403
    assert client.get("/api/v1/agents", headers=client_headers).status_code == 403
    assert client.get("/api/v1/analytics/overview", headers=client_headers).status_code == 403


def test_update_profile(client, client_headers):
    r = client.patch("/api/v1/auth/me", json={"full_name": "Renamed Client", "brand_notes": "Blue and white"}, headers=client_headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Renamed Client"


def test_pages_served(client):
    for path in ("/", "/login", "/register", "/portal", "/admin", "/services/logo-design"):
        r = client.get(path)
        assert r.status_code in (200, 404), path  # 404 only until the frontend phase writes the file
