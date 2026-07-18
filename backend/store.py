from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


class JsonStore:
    def __init__(self, path: Path):
        self.path = path
        if not self.path.exists():
            self.path.write_text(json.dumps({"lights": [], "queries": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def insert_light(self, light: dict[str, Any]) -> None:
        data = self._read()
        data["lights"].append(light)
        self._write(data)

    def list_lights(self) -> list[dict[str, Any]]:
        return self._read()["lights"]

    def get_light(self, light_id: str) -> dict[str, Any] | None:
        for light in self._read()["lights"]:
            if light["id"] == light_id:
                return light
        return None

    def patch_light(self, light_id: str, patch: dict[str, Any], updated_at: str) -> dict[str, Any] | None:
        data = self._read()
        for idx, light in enumerate(data["lights"]):
            if light["id"] == light_id:
                light.update(patch)
                light["updated_at"] = updated_at
                data["lights"][idx] = light
                self._write(data)
                return light
        return None

    def insert_query(self, query: dict[str, Any]) -> None:
        data = self._read()
        data["queries"].append(query)
        self._write(data)

    def get_query(self, query_id: str) -> dict[str, Any] | None:
        for q in self._read()["queries"]:
            if q["id"] == query_id:
                return q
        return None


def image_embedding(image: Image.Image) -> list[float]:
    img = image.convert("RGB").resize((128, 128))
    arr = np.asarray(img, dtype=np.float32)
    hist_r, _ = np.histogram(arr[:, :, 0], bins=16, range=(0, 255), density=True)
    hist_g, _ = np.histogram(arr[:, :, 1], bins=16, range=(0, 255), density=True)
    hist_b, _ = np.histogram(arr[:, :, 2], bins=16, range=(0, 255), density=True)
    emb = np.concatenate([hist_r, hist_g, hist_b])
    norm = np.linalg.norm(emb)
    if norm == 0:
        return emb.tolist()
    return (emb / norm).tolist()


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
