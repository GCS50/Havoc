"""The web UI is served by the API app."""


async def test_index_is_served(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "/static/app.js" in resp.text


async def test_static_assets_are_served(client):
    for path in ("/static/app.js", "/static/styles.css"):
        resp = await client.get(path)
        assert resp.status_code == 200, path
