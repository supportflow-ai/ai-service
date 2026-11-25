# SupportFlow AI Service

Dịch vụ cung cấp API nội bộ để gợi ý phân loại phiếu. Theo `AI-02`, mô hình phân loại học máy cục bộ và luồng người có quyền duyệt được nghiệm thu cùng Identity và Ticketing. Backend ghi kết quả và audit. Provider `rule` phục vụ kiểm thử tích hợp trong khi nhóm chọn mô hình và nối luồng đầu cuối. Bộ checkout liên kho có phạm vi và tiêu chí nghiệm thu trong `supportflow-ai-infra/docs/project/mvp.md`.

## Pipeline Knowledge Published — 05/11/2026

Hồ sơ TC-346–TC-350 ngày 05/11 ghi kiểm thử trên nguyên mẫu local, gồm prepare phía AI và thử tích hợp job, Worker và lưu vector phía Backend. Kết quả thuộc working tree của lần thử đó.

Tại mốc 21/11, Backend `dev@3640c33` chưa có hợp đồng nguồn, migration hay consumer prepare. Việc nối Backend thuộc `AI-09`. Truy hồi ngữ nghĩa và RAG ở mốc riêng. [Thiết kế và hiện trạng prepare](docs/knowledge-index-pipeline.md) · [Kết quả lịch sử ngày 05/11](docs/knowledge-index-verification.md)

## Hiện trạng

AI Service `main@207d26d` có hai API nội bộ qua Bearer dịch vụ. `POST /v1/ticket-classifications` dùng OpenAPI phân loại v1. `POST /v1/knowledge-indexes:prepare` dùng hợp đồng Knowledge riêng. `rule` là provider luật hiện có. `noop` là mặc định và trả `503` ở readiness phân loại. `local-e5` thuộc cấu hình embedding, chạy E5 cục bộ trên CPU trong image stage `embeddings`.

Docker cài runtime theo phiên bản ghim trong `requirements-runtime.lock`. Dependency kiểm
thử nằm trong `pyproject.toml`. Production yêu cầu token dịch vụ riêng. Schema v1 kiểm tra
chặt kiểu của `ticketRevision` ở cả request và response.

Chỉ mục tài liệu rà ngày 21/11/2026 tại AI Service `main@207d26d`. Các mốc Backend trong tài liệu đối chiếu ghi theo lần đọc tương ứng.

- Tích hợp phân loại theo [đối chiếu Backend–AI](docs/backend-alignment.md), [bản ghim v1](contract.lock.json) và [kiến trúc AI Service](docs/architecture.md).
- Chuẩn bị thực nghiệm theo [kế hoạch classifier](docs/ml-classifier-plan.md), [đặc tả dữ liệu đánh giá](evaluation/DATASET.md) và bộ TL01–TL06 trong `docs/audit/2026-11-21/chuan-hoa-tai-lieu-ai-service.md` của workspace liên kho.
- Khi đổi lưu trữ, xem [tác động R2 đối với AI Service](docs/r2-impact.md). Quy trình làm việc nằm trong [cẩm nang chung](docs/team-handbook.md) và [quy tắc của kho](AGENTS.md).

## Trách nhiệm

AI service:

- chạy ticket classification;
- giữ provider/model adapters tách khỏi API;
- tạo nền cho embedding;
- cung cấp evaluation baseline;
- không kết nối Service Desk database;
- không thay đổi ticket, priority, permission hoặc workflow.

Backend ASP.NET Core vẫn sở hữu business state, authorization, HITL, persistence và audit.

## Kiến trúc

```text
FastAPI
  |
  v
Application use cases
  |
  v
Ports <---- Adapters
  |          |-- NoOp
  |          `-- Rule baseline
  v
Domain
```

Xem `docs/architecture.md`.

## Trạng thái capability

| Capability | Trạng thái |
|---|---|
| Classification contract v1 | Có |
| FastAPI classification endpoint | Có |
| Service Bearer auth | Có |
| NoOp provider / controlled 503 | Có |
| Rule-based baseline | Category theo từ khóa, gồm `OTHER` cho từ khóa máy chủ/hạ tầng. Rubric E0 có thể gợi ý Impact/Urgency ở mức `High` |
| Không có gợi ý | Bỏ trường thiếu tín hiệu. Trả `suggestions: []` khi không có tín hiệu ở cả ba trường |
| Tín hiệu giải thích | Chưa có |
| Che dữ liệu cá nhân (PII) cho dữ liệu huấn luyện | Chưa có |
| Model phân loại học máy | Chưa chọn (dùng rule baseline) |
| Embedding CPU E5 và chuẩn bị chỉ mục Knowledge | Có (`POST /v1/knowledge-indexes:prepare`, `GET /health/embedding`); backend chưa tiêu thụ |
| Tìm kiếm ngữ nghĩa, truy vấn embedding | Chưa có |
| RAG | Chưa đưa vào MVP |
| Evaluation baseline | Có, trên 11 mẫu smoke (`evaluation/sample-classification.jsonl`), chưa có gold set |

## Chạy local

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

python -m pip install -r requirements-runtime.lock -r requirements-ml.txt -e ".[dev]"
cp .env.example .env
# Sinh token riêng, sao chép kết quả vào SUPPORTFLOW_AI_SERVICE_TOKEN trong .env:
python -c "import secrets; print(secrets.token_urlsafe(48))"
uvicorn supportflow_ai.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

PowerShell có thể dùng:

```powershell
Copy-Item .env.example .env
```

Hai POST dưới đây là API nội bộ. Ba GET kiểm tiến trình, phân loại và embedding riêng:

```text
POST /v1/ticket-classifications
POST /v1/knowledge-indexes:prepare   (S2S, chuẩn bị chỉ mục Knowledge)
GET  /health/live
GET  /health/ready
GET  /health/embedding
```

Request và response minh họa lấy từ [fixture phân loại v1](contracts/ai/v1/fixtures.json):

```json
{
  "requestId": "00000000-0000-0000-0000-000000000001",
  "ticketId": "00000000-0000-0000-0000-000000000002",
  "ticketRevision": 1,
  "inputHash": "e737e044b7ef976a6f2f2e97f1f2aaee633a2205cc16d051316bf2139d5dc02c",
  "title": "VPN issue",
  "description": "Cannot connect"
}
```

```json
{
  "requestId": "00000000-0000-0000-0000-000000000001",
  "ticketId": "00000000-0000-0000-0000-000000000002",
  "ticketRevision": 1,
  "inputHash": "e737e044b7ef976a6f2f2e97f1f2aaee633a2205cc16d051316bf2139d5dc02c",
  "suggestions": [
    {
      "field": "category",
      "value": "VPN",
      "score": null
    }
  ]
}
```

Header:

```text
Authorization: Bearer <SUPPORTFLOW_AI_SERVICE_TOKEN>
```

Backend tính `inputHash` từ tiêu đề và mô tả. Nếu đổi nội dung, dùng hash do Backend tính lại. Phản hồi trả lại `requestId`, `ticketId`, `ticketRevision` và `inputHash`. `suggestions` chứa tối đa một phần tử `field/value/score` cho mỗi trường. Gợi ý từ `rule` dùng `score: null`. Nếu thiếu tín hiệu ở mọi trường, phản hồi có mảng gợi ý rỗng. [Ranh giới hợp đồng và bảng readiness](docs/architecture.md#contract-boundary)

## Kiểm thử

```bash
ruff check .
pytest
python scripts/validate_ai_contract.py
python -m evaluation.run_classification
python -m compileall -q src evaluation scripts
```

`evaluation/sample-classification.jsonl` chỉ là smoke data, không phải gold set.

### Kiểm tra image và HTTP

`make docker-build` tạo image local `ghcr.io/supportflow-ai/ai-service:local`. CI dùng cùng
tên image với quy trình phát hành của infra và gắn tag `sha-<commit>`. Bước
**Xác minh HTTP trong container** chạy image trên Linux, gọi qua `127.0.0.1:8000` từ
trong container và ghi kết quả từng ca cùng SHA và image ID trong log.

| Ca kiểm tra | Kỳ vọng |
|---|---|
| Liveness của `rule` và `noop` | HTTP 200 |
| Readiness của `rule` | HTTP 200 |
| Snapshot VPN và SEC | HTTP 200, đúng danh mục và đủ `requestId`, `ticketId`, `ticketRevision`, `inputHash` |
| Bearer sai | HTTP 401 |
| Revision kiểu boolean | HTTP 400 |
| Payload vượt giới hạn | HTTP 413 |
| Readiness của `noop` | HTTP 503 |

Để chạy lại, dùng các lệnh trong bước CI trên và đặt `AI_IMAGE` thành tag local. Smoke test
dùng token tạm, payload giả và mạng `none` chỉ có loopback. Log không ghi token hoặc nội
dung ticket. Job phát hành GHCR cần dispatch riêng với `publish_images=true` trên
`main` hoặc `dev`, sau khi các bước kiểm tra đạt.

Workflow [41584086425](https://github.com/supportflow-ai/ai-service/actions/runs/41584086425)
ghi nhận lỗi import `evaluation.metrics` khi thu thập test tại `134c9d2`. Pytest được cấu
hình thêm gốc dự án để import package evaluation khi chạy bằng lệnh `pytest`. Dùng log
của đúng SHA ứng viên để xác nhận kết quả kiểm thử và build.

## Provider mới

Để thêm model thật:

1. triển khai `TicketClassifier` trong `src/supportflow_ai/adapters/classifiers/`;
2. giữ provider output trong domain `ClassificationPrediction`;
3. đăng ký provider trong `bootstrap.py`;
4. thêm contract/integration tests;
5. benchmark cùng gold set trước khi chọn làm mặc định.

Không gọi SDK model trực tiếp từ FastAPI route.

## Security

- Không truyền end-user JWT sang AI service.
- Không cấp DB credential nghiệp vụ cho AI service.
- Không log title/description.
- Không trả action đặc quyền.
- Mặc định xác thực bật và **không có token mặc định**. Nếu không cung cấp token hợp lệ,
service sẽ từ chối khởi động. Chỉ môi trường development/test mới có thể tắt auth một cách
rõ ràng để chạy thử; staging/production không cho phép. Giới hạn request-body 64 KiB.

Production phải bật service Bearer với secret ngoài Git; đặt service trên private network,
không mở public port. Chưa có distributed rate-limit/advanced credential rotation/mTLS.
