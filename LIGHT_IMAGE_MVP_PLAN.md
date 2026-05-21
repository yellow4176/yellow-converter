# 조명 이미지 수배 MVP 설계서

## 목표
업로드된 조명 이미지에서 조명 후보를 찾아 제조사/품목/사이즈/색온도 등의 정보를 반환하는 MVP를 정의한다.

## 기능 범위 (MVP)
1. 이미지 업로드 (다중 이미지)
2. 조명 객체 탐지 및 임베딩 생성
3. 유사도 기반 후보 검색
4. 후보 메타데이터 반환 (제조사, 품목, 사이즈, 색온도)
5. 관리자 검수 화면에서 정답 보정/승인

## 시스템 아키텍처
- Frontend: Next.js
- Backend API: FastAPI
- Metadata DB: PostgreSQL
- Vector Search: pgvector
- Object Storage: S3 호환 저장소
- Async Worker: Celery/RQ (선택)

## 데이터 모델
### lights
- id (UUID, PK)
- manufacturer (TEXT)
- model_name (TEXT)
- category (TEXT)
- size_mm (JSONB)
- cct_k (INT[])
- cri (INT)
- lumen (INT)
- finish_color (TEXT)
- source_url (TEXT)
- verified (BOOLEAN)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

### light_images
- id (UUID, PK)
- light_id (UUID, FK)
- image_url (TEXT)
- view_type (TEXT)
- bbox (JSONB)
- embedding (vector)
- created_at (TIMESTAMP)

### search_queries
- id (UUID, PK)
- input_image_urls (JSONB)
- status (TEXT: queued/running/done/error)
- topk_result (JSONB)
- created_at (TIMESTAMP)

## API 초안
- POST /api/v1/search/upload
  - multipart/form-data: images[]
  - response: { query_id, status }
- GET /api/v1/search/{query_id}
  - response: { query_id, status, results[] }
- GET /api/v1/lights/{light_id}
- PATCH /api/v1/admin/lights/{light_id}
- POST /api/v1/admin/lights

## 추론 파이프라인
1. 업로드 이미지 수신
2. 조명 객체 detection
3. bbox crop 임베딩 생성
4. vector top-k 검색
5. OCR 텍스트 매칭(브랜드/모델명 보강)
6. 재랭킹(유사도 + OCR + category 규칙)
7. 결과 반환 및 로그 저장

## 신뢰도 정책
- 제조사/모델명: OCR/라벨 근거가 있으면 높은 신뢰도
- 색온도: 촬영환경 영향이 커서 추정 범위로 제공
- 사이즈: 스케일 기준이 없으면 중/저 신뢰도로 표기

## 4주 일정
### 1주차
- DB 스키마, 업로드 API, 파일 저장

### 2주차
- 임베딩 저장/검색, 결과 API

### 3주차
- OCR + 재랭킹, 관리자 검수 UI

### 4주차
- 신뢰도 노출, 로깅/모니터링, 파일럿 검증

## 성공 지표
- Top-5 후보 내 정답 포함률(Recall@5)
- 평균 응답 시간(p95)
- 관리자 검수 후 최종 정확도

## 리스크 및 대응
- 동일 디자인의 OEM 제품 구분 어려움
  - 대응: 로고/OCR, 출처 URL 기반 검증
- 색온도/사이즈 오차
  - 대응: 추정치 표기 + 다각도 추가 업로드 유도
