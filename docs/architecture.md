# Kiến trúc AI Service

## Mục tiêu

`ai-service` là dịch vụ suy luận **không trạng thái**, không phải backend nghiệp vụ thứ hai.

Backend ASP.NET Core là hệ thống lưu trữ chính và sở hữu: xác thực và phân quyền người dùng, vòng
đời phiếu, taxonomy nghiệp vụ, Priority (`PriorityMatrix`) và dải tin cậy (`ConfidencePolicy`), lưu
`AIAnalysis`/`AISuggestion`, chấp nhận/sửa/từ chối gợi ý, định tuyến (`RoutingRule`), Knowledge Base
và audit.

AI service chỉ sở hữu năng lực suy luận:

- phân loại phiếu: gợi ý Category, Impact, Urgency theo hợp đồng v1;
- chuẩn bị chỉ mục Knowledge (chia khối Markdown, embedding E5 cục bộ). Knowledge là P2, ngoài MVP
  (tài liệu kiến trúc v3.0, 15/11/2026): mã giữ nguyên, không phát triển thêm;
- adapter của các provider và mã đánh giá.

Mọi provider chạy cục bộ; **không gọi API hay dịch vụ model bên ngoài** (chủ dự án chốt 2026-11-13).

## Hướng phụ thuộc

```text
api (routes, schemas, auth, middleware, errors)
  -> application (ClassifyTicket, PrepareKnowledgeIndex)
    -> ports (TicketClassifier, BatchEmbedder, MarkdownChunker, TextTokenizer)
         ^
       adapters (classifiers/rule_based, noop, ml/*; embedders/local_e5; markdown_chunker)
    domain (Category/Impact/Urgency, Suggestion, ClassificationPrediction; bất biến hợp đồng)

bootstrap.py  chọn và dựng mọi provider theo cấu hình
main.py       create_app: gọi bootstrap, gắn middleware, handler lỗi, router
```

`domain`, `application`, `ports` không import FastAPI, Starlette, torch, transformers, `api`,
`adapters` hay `config`; gói `supportflow_ai` không import `evaluation` hay `training`. Hai ranh giới
này được canh bởi `tests/unit/test_architecture_boundaries.py`.

## Ranh giới hợp đồng

| Endpoint | Hợp đồng | Ghi chú |
| --- | --- | --- |
| `POST /v1/ticket-classifications` | `contracts/ai/v1/openapi.yaml`, Backend là chủ sở hữu, ghim byte và SHA trong `contract.lock.json` | Tối đa 3 gợi ý, mỗi trường 1, `score` trong [0, 1] hoặc `null` |
| `POST /v1/knowledge-indexes:prepare` | `contracts/ai/knowledge-index/v1` (bản sao, Backend chưa có bản chuẩn) | Chỉ S2S |
| `GET /health/live`, `/health/ready`, `/health/embedding` | Không thuộc hợp đồng; infra và `scripts/smoke_http.py` dựa vào mã trạng thái và body | `/health/ready` trả 503 khi `classifier.ready` là `False` |

Không thêm `priority`, `status`, `assignment`, `actions`, vai trò hay lệnh workflow vào response.
Body request bị giới hạn ở tầng ASGI (`LimitRequestBodyMiddleware`, mặc định 64 KiB).

## Provider phân loại

Port `TicketClassifier` (`ports/classifier.py`) có `name`, `ready`, `model_version` và
`async classify(title, description)`.

| Provider | `ready` | Điểm | Ghi chú |
| --- | --- | --- | --- |
| `noop` (mặc định khi không cấu hình) | `False` | | Trả 503 `provider_unavailable` có kiểm soát |
| `rule` | `True` | `null` | Từ khóa cho Category; rubric E0 chỉ phát `High` cho Impact/Urgency |
| `ml` (kế hoạch, mốc M3) | Theo kết quả tải artifact | Đã hiệu chỉnh hoặc `null` | Khung ở `adapters/classifiers/ml/` |

Khung `adapters/classifiers/ml/` (chưa đăng ký làm provider):

- `text.py`: chuẩn hóa và cắt văn bản, dùng chung cho huấn luyện và suy luận; `PREPROCESSING_VERSION`
  được ghi vào manifest để chặn lệch tiền xử lý.
- `artifact.py`: đọc `manifest.json`, kiểm SHA-256 từng file, chặn đường dẫn ra ngoài thư mục mô hình,
  kiểm ngưỡng abstain theo từng trường.
- `inference.py`: `BoundedInference` chạy suy luận trong executor riêng, giới hạn số luồng và độ sâu
  hàng chờ, quá thời gian chờ thì trả 503 `classifier_busy`. Thiết kế tính tới việc adapter Backend
  retry một lần khi gặp 503 và mở ngắt mạch sau 3 lỗi liên tiếp.

Truy vết: log `classification_completed` ghi `provider` và `model_version` (khi có), không ghi nội
dung phiếu. Header phiên bản mô hình trong response đang chờ Backend duyệt
([ml-classifier-plan.md](ml-classifier-plan.md) mục 4.3); body hợp đồng v1 không đổi.

## Embedding và Knowledge

`bootstrap.build_knowledge_index_preparer` chỉ dựng `PrepareKnowledgeIndex` khi
`SUPPORTFLOW_AI_EMBEDDING_PROVIDER=local-e5`; adapter `LocalE5Embedder` được import muộn vì chỉ image
`embeddings` có `sentence-transformers` và torch. Không bật thì endpoint và `/health/embedding` trả 503.
Chi tiết: [knowledge-index-pipeline.md](knowledge-index-pipeline.md).

RAG chưa thuộc phạm vi. Nếu mở lại, retrieval và kiểm quyền ở Backend (pgvector), AI service không truy
cập trực tiếp PostgreSQL của Service Desk.

## Tiến hóa provider

```text
classification: noop -> rule baseline -> ml cục bộ (TF-IDF + tuyến tính hoặc PhoBERT, chọn theo đánh giá)
embedding:      noop -> local-e5 (đóng băng cùng Knowledge)
```

Mỗi provider triển khai port riêng; hợp đồng HTTP và use case không đổi. Kế hoạch:
[ml-classifier-plan.md](ml-classifier-plan.md).
