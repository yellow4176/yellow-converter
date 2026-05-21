from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from PIL import Image

from backend.store import JsonStore, cosine_similarity, image_embedding

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = BASE_DIR / "light_store.json"

app = FastAPI(title="Lighting Image Sourcing API", version="0.1.0")
store = JsonStore(STORE_PATH)


class SearchResult(BaseModel):
    light_id: str
    score: float
    manufacturer: str | None = None
    model_name: str | None = None
    category: str | None = None
    size_mm: dict | None = None
    cct_k: List[int] | None = None


class SearchResponse(BaseModel):
    query_id: str
    status: str
    results: List[SearchResult]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/v1/admin/lights")
async def register_light(
    manufacturer: str,
    model_name: str,
    category: str = "unknown",
    cct_k: str = "[]",
    size_mm: str = "{}",
    image: UploadFile = File(...),
) -> dict:
    light_id = str(uuid.uuid4())
    image_path = UPLOAD_DIR / f"{light_id}_{image.filename}"
    raw = await image.read()
    image_path.write_bytes(raw)

    emb = image_embedding(Image.open(image_path))

    light = {
        "id": light_id,
        "manufacturer": manufacturer,
        "model_name": model_name,
        "category": category,
        "cct_k": json.loads(cct_k),
        "size_mm": json.loads(size_mm),
        "image_path": str(image_path),
        "embedding": emb,
        "created_at": datetime.utcnow().isoformat(),
    }
    store.insert_light(light)
    return {"light_id": light_id, "status": "created"}


@app.post("/api/v1/search/upload", response_model=SearchResponse)
async def search_lights(images: List[UploadFile] = File(...)) -> SearchResponse:
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")

    query_id = str(uuid.uuid4())
    candidates = store.list_lights()
    if not candidates:
        return SearchResponse(query_id=query_id, status="done", results=[])

    merged_results: dict[str, float] = {}

    for image in images:
        temp_path = UPLOAD_DIR / f"query_{query_id}_{image.filename}"
        temp_path.write_bytes(await image.read())
        q_emb = image_embedding(Image.open(temp_path))

        for light in candidates:
            score = cosine_similarity(q_emb, light["embedding"])
            prev = merged_results.get(light["id"], -1.0)
            merged_results[light["id"]] = max(prev, score)

    ranked = sorted(merged_results.items(), key=lambda x: x[1], reverse=True)[:5]
    results: List[SearchResult] = []
    for light_id, score in ranked:
        light = store.get_light(light_id)
        if not light:
            continue
        results.append(
            SearchResult(
                light_id=light_id,
                score=round(score, 4),
                manufacturer=light.get("manufacturer"),
                model_name=light.get("model_name"),
                category=light.get("category"),
                size_mm=light.get("size_mm"),
                cct_k=light.get("cct_k"),
            )
        )

    store.insert_query({
        "id": query_id,
        "status": "done",
        "result_ids": [r.light_id for r in results],
        "created_at": datetime.utcnow().isoformat(),
    })

    return SearchResponse(query_id=query_id, status="done", results=results)


@app.get("/api/v1/search/{query_id}")
def get_query(query_id: str) -> dict:
    query = store.get_query(query_id)
    if not query:
        raise HTTPException(status_code=404, detail="query not found")
    return query


@app.get("/api/v1/lights/{light_id}")
def get_light(light_id: str) -> dict:
    light = store.get_light(light_id)
    if not light:
        raise HTTPException(status_code=404, detail="light not found")
    return light
