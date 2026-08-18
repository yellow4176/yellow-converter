from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from backend.main import app

client = TestClient(app)


def _img_bytes(color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (32, 32), color)
    bio = BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_register_and_search_flow():
    files = {"image": ("lamp_red.png", _img_bytes((255, 0, 0)), "image/png")}
    data = {
        "manufacturer": "TestCo",
        "model_name": "RedLamp",
        "category": "pendant",
        "cct_k": "[3000]",
        "size_mm": '{"diameter":120}',
    }
    reg = client.post("/api/v1/admin/lights", files=files, data=data)
    assert reg.status_code == 200
    light_id = reg.json()["light_id"]

    search = client.post(
        "/api/v1/search/upload",
        files=[("images", ("query.png", _img_bytes((254, 0, 0)), "image/png"))],
    )
    assert search.status_code == 200
    body = search.json()
    assert body["results"]
    assert body["results"][0]["light_id"] == light_id


def test_patch_light_metadata():
    files = {"image": ("lamp_blue.png", _img_bytes((0, 0, 255)), "image/png")}
    data = {
        "manufacturer": "BlueCo",
        "model_name": "BlueLamp",
        "cct_k": "[4000]",
        "size_mm": "{}",
    }
    reg = client.post("/api/v1/admin/lights", files=files, data=data)
    light_id = reg.json()["light_id"]

    patched = client.patch(f"/api/v1/admin/lights/{light_id}", json={"manufacturer": "BlueCoNew", "cct_k": [5000]})
    assert patched.status_code == 200
    detail = client.get(f"/api/v1/lights/{light_id}")
    assert detail.json()["manufacturer"] == "BlueCoNew"
    assert detail.json()["cct_k"] == [5000]
