"""SPA fallback must serve the React shell for admin routes."""


def test_admin_paths_serve_spa(client):
    for path in ("/admin", "/admin/login", "/admin/sessions"):
        res = client.get(path)
        assert res.status_code == 200, path
        assert b"spa-ok" in res.data


def test_homepage_serves_spa(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"spa-ok" in res.data
