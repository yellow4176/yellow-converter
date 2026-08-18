# Lighting Image Sourcing API (MVP)

## Run
```bash
uvicorn backend.main:app --reload
```

## Endpoints
- `POST /api/v1/admin/lights` : 기준 조명 등록(이미지 + 메타)
- `POST /api/v1/search/upload` : 검색 이미지 업로드 후 유사 조명 Top-5 반환
- `GET /api/v1/lights/{light_id}` : 조명 상세 조회
- `GET /api/v1/search/{query_id}` : 검색 로그 조회

## Notes
- 현재 임베딩은 색상 히스토그램 기반의 MVP 방식입니다.
- 다음 단계로 CLIP 임베딩 + pgvector로 교체하면 정확도가 크게 향상됩니다.
