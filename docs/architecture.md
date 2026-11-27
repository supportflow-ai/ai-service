# Kiến trúc AI Service

> Phần mô tả gốc giữ mốc đối chiếu bên dưới. Các mục bổ sung theo `main@09ca691` ở cuối ghi cấu trúc provider, readiness và truy vết đã có ở mốc mới.

## Mục tiêu

`ai-service` xử lý suy luận không trạng thái. Mốc đối chiếu ngày 21/11/2026 gồm AI Service `main@207d26d`, Backend `dev@3640c33` và Web `dev@89eabc4`. Backend sở hữu dữ liệu và quyền nghiệp vụ.

Backend ASP.NET Core vẫn là system of record và sở hữu:

- authentication / authorization;
- ticket lifecycle;
- taxonomy nghiệp vụ;
- priority và confidence band;
- thiết kế lưu `AIAnalysis`/`AISuggestion` và ghi quyết định duyệt khi nối luồng phân loại;
- Knowledge Base và quyền truy cập;
- audit.

AI service chỉ sở hữu inference capabilities:

- phân loại phiếu theo hợp đồng v1;
- chia khối và tạo embedding từ snapshot Knowledge qua endpoint prepare;
- model/provider adapters;
- evaluation code.

## Dependency direction

```text
API -> Application -> Ports <- Adapters
                    |
                  Domain
```

Domain/Application không phụ thuộc FastAPI, SDK model hay database.

## Contract boundary

Hai API nội bộ hiện có dùng Bearer dịch vụ:

```text
POST /v1/ticket-classifications
POST /v1/knowledge-indexes:prepare
```

`POST /v1/ticket-classifications` dùng bản ghim của hợp đồng Backend. `requestId` và `ticketId` là UUID, `ticketRevision` là số nguyên không âm, `inputHash` gồm 64 chữ số hex thường. Backend tính hash từ tiêu đề và mô tả. AI Service kiểm định dạng rồi trả lại hash cùng các trường tương quan còn lại. Backend kiểm bốn giá trị khi nhận phản hồi.

`suggestions` là mảng phần tử `field/value/score` và có tối đa một gợi ý cho mỗi `category`, `impact`, `urgency`. Mảng rỗng thể hiện không có gợi ý. Điểm là số hữu hạn trong [0, 1] hoặc `null`. Provider `rule` gợi ý Category theo từ khóa, gồm `OTHER` cho ca khớp từ khóa máy chủ/hạ tầng. Rubric E0 có thể gợi ý `High` cho Impact/Urgency. Bỏ trường thiếu tín hiệu và trả mảng rỗng nếu không có gợi ý. Điểm của gợi ý theo luật là `null`. Mức ưu tiên và điều phối thuộc Backend. [OpenAPI và fixture v1](../contracts/ai/v1/README.md)

Xác thực mặc định bật. Chỉ cấu hình `development` và `test` cho phép tắt. Request body được giới hạn ở tầng ASGI, mặc định 64 KiB cho phân loại và cố định 1 MiB cho prepare. [Cấu hình](../src/supportflow_ai/config.py) · [Giới hạn request](../src/supportflow_ai/api/middleware.py)

## Kiểm tra sức khỏe

| Endpoint | Phạm vi kiểm tra |
| --- | --- |
| `GET /health/live` | Tiến trình phản hồi `200` |
| `GET /health/ready` | Phân loại. `rule` trả `200`, `noop` trả `503`. `ml` trả `200` khi artifact đã kiểm SHA nạp được, `503` khi không |
| `GET /health/embedding` | Chuẩn bị embedding. Trả `200` khi bộ prepare sẵn sàng, `503` khi chưa có hoặc chưa sẵn sàng |

Các route sức khỏe hiện không dùng Bearer dịch vụ. Readiness của từng năng lực chỉ mô tả AI Service. Bằng chứng tích hợp Backend, Web và mô hình ứng viên được ghi ở mốc nghiệm thu. [Route sức khỏe](../src/supportflow_ai/api/routes/health.py)

## Embedding

`POST /v1/knowledge-indexes:prepare` kiểm snapshot bài viết và profile, chia khối và trả vector 384 chiều khi dùng `local-e5`. Provider này chỉ dùng cho embedding. Cấu hình mặc định `noop` làm prepare trả `503`. Hợp đồng Knowledge ở `contracts/ai/knowledge-index/v1/` thuộc bề mặt API riêng. AI Service hiện có bộ đặc tả và fixture, còn chờ nguồn chuẩn từ Backend để ghim. Backend giữ `IEmbeddingService` NoOp và chưa có consumer prepare, job hay lưu vector. Mốc kết nối thuộc `AI-09`. [Thiết kế và hiện trạng Knowledge](knowledge-index-pipeline.md)

## RAG

Truy hồi ngữ nghĩa và RAG thuộc thiết kế sau. Khi xem xét mở rộng, đặt ranh giới phân quyền dữ liệu trước khi đưa nguồn vào bước xếp hạng hoặc sinh câu trả lời:

```text
Embedding -> Retrieval theo phạm vi được cấp quyền (Backend) -> Reranking -> Generation
```

AI service không truy cập trực tiếp Service Desk PostgreSQL.

## Provider evolution

```text
classification: noop | rule | ml
embedding:      noop | local-e5
```

Hai cấu hình độc lập và đều mặc định `noop`. Provider `ml` đã đăng ký, nhưng chưa có artifact ứng viên được chọn và đánh giá theo `AI-07`. Ngày 13/11/2026 chủ dự án chốt inference cục bộ. `AI-02` yêu cầu phân loại có người duyệt cùng Identity và Ticketing trên một ứng viên. [Kế hoạch phân loại](ml-classifier-plan.md) · [Đối chiếu hai dịch vụ](backend-alignment.md)

## Bổ sung kỹ thuật tại `main@09ca691`

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
| `ml` | Theo kiểm tra artifact lúc nạp. `dev-stub` chỉ nạp khi `SUPPORTFLOW_AI_ALLOW_DEV_STUB` bật (development, test) | `null`, trừ artifact `candidate` đã hiệu chỉnh | Đăng ký ở `bootstrap.py`, mã ở `adapters/classifiers/ml/` |

Adapter `adapters/classifiers/ml/` (đã đăng ký ở `bootstrap.py`):

- `provider.py`: `MlClassifier` nạp artifact lúc khởi động. Lỗi artifact hoặc môi trường làm `ready` là `False`, app vẫn chạy và `/health/ready` trả 503. Impact và Urgency mức `High` lấy từ rubric E0, độc lập với mô hình Category.
- `contract_pin.py`: SHA-256 của hợp đồng v1 đã ghim. Manifest có `classificationContractSha256` khác hằng số này bị từ chối.
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
