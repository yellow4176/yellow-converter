from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError

from backend.store import JsonStore, cosine_similarity, image_embedding

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = BASE_DIR / "light_store.json"

app = FastAPI(title="Lighting Image Sourcing API", version="0.2.0")
store = JsonStore(STORE_PATH)


class SearchResult(BaseModel):
    light_id: str
    score: float
    manufacturer: str | None = None
    model_name: str | None = None
    category: str | None = None
    size_mm: dict[str, Any] | None = None
    cct_k: list[int] | None = None


class SearchResponse(BaseModel):
    query_id: str
    status: str
    results: list[SearchResult]


class LightPatchRequest(BaseModel):
    manufacturer: str | None = None
    model_name: str | None = None
    category: str | None = None
    cct_k: list[int] | None = None
    size_mm: dict[str, Any] | None = None


class LightRecord(BaseModel):
    id: str
    manufacturer: str
    model_name: str
    category: str = "unknown"
    cct_k: list[int] = Field(default_factory=list)
    size_mm: dict[str, Any] = Field(default_factory=dict)
    image_path: str
    embedding: list[float]
    created_at: str
    updated_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_image(path: Path) -> Image.Image:
    try:
        img = Image.open(path)
        img.verify()
        return Image.open(path)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Invalid image file") from exc


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "time": utc_now_iso()}


@app.post("/api/v1/admin/lights")
async def register_light(
    manufacturer: Annotated[str, Form(...)],
    model_name: Annotated[str, Form(...)],
    category: Annotated[str, Form()] = "unknown",
    cct_k: Annotated[str, Form()] = "[]",
    size_mm: Annotated[str, Form()] = "{}",
    image: UploadFile = File(...),
) -> dict[str, str]:
    light_id = str(uuid.uuid4())
    filename = image.filename or "upload.jpg"
    image_path = UPLOAD_DIR / f"{light_id}_{Path(filename).name}"
    image_path.write_bytes(await image.read())

    try:
        parsed_cct = json.loads(cct_k)
        parsed_size = json.loads(size_mm)
        if not isinstance(parsed_cct, list) or not isinstance(parsed_size, dict):
            raise ValueError("Wrong metadata type")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="cct_k must be JSON list and size_mm JSON object") from exc

    emb = image_embedding(_validate_image(image_path))

    now = utc_now_iso()
    light = LightRecord(
        id=light_id,
        manufacturer=manufacturer.strip(),
        model_name=model_name.strip(),
        category=category.strip(),
        cct_k=parsed_cct,
        size_mm=parsed_size,
        image_path=str(image_path),
        embedding=emb,
        created_at=now,
        updated_at=now,
    )
    store.insert_light(light.model_dump())
    return {"light_id": light_id, "status": "created"}


@app.patch("/api/v1/admin/lights/{light_id}")
def patch_light(light_id: str, payload: LightPatchRequest) -> dict[str, Any]:
    updated = store.patch_light(light_id, payload.model_dump(exclude_none=True), utc_now_iso())
    if updated is None:
        raise HTTPException(status_code=404, detail="light not found")
    return updated


@app.post("/api/v1/search/upload", response_model=SearchResponse)
async def search_lights(images: list[UploadFile] = File(...)) -> SearchResponse:
    if not images:
        raise HTTPException(status_code=400, detail="No images provided")

    query_id = str(uuid.uuid4())
    candidates = store.list_lights()
    if not candidates:
        return SearchResponse(query_id=query_id, status="done", results=[])

    merged_results: dict[str, float] = {}

    for idx, image in enumerate(images):
        filename = image.filename or f"image_{idx}.jpg"
        temp_path = UPLOAD_DIR / f"query_{query_id}_{Path(filename).name}"
        temp_path.write_bytes(await image.read())
        q_emb = image_embedding(_validate_image(temp_path))

        for light in candidates:
            score = cosine_similarity(q_emb, light["embedding"])
            prev = merged_results.get(light["id"], -1.0)
            merged_results[light["id"]] = max(prev, score)

    ranked = sorted(merged_results.items(), key=lambda x: x[1], reverse=True)[:5]
    results: list[SearchResult] = []
    for light_id, score in ranked:
        light = store.get_light(light_id)
        if light is None:
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

    store.insert_query(
        {
            "id": query_id,
            "status": "done",
            "result_ids": [r.light_id for r in results],
            "created_at": utc_now_iso(),
        }
    )

    return SearchResponse(query_id=query_id, status="done", results=results)


@app.get("/api/v1/search/{query_id}")
def get_query(query_id: str) -> dict[str, Any]:
    query = store.get_query(query_id)
    if query is None:
        raise HTTPException(status_code=404, detail="query not found")
    return query


@app.get("/api/v1/lights/{light_id}")
def get_light(light_id: str) -> dict[str, Any]:
    light = store.get_light(light_id)
    if light is None:
        raise HTTPException(status_code=404, detail="light not found")
    return light
