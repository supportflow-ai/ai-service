# SupportFlow AI Service

## Hiện trạng

AI-service cung cấp API phân loại ticket theo OpenAPI v1 của **SupportFlow AI IT Service
Desk**. Provider `rule` phân loại theo từ khóa, còn `noop` trả readiness 503. Dự án chưa
tích hợp model học máy hoặc dịch vụ model bên ngoài.

Docker cài runtime theo phiên bản ghim trong `requirements-runtime.lock`. Dependency kiểm
thử nằm trong `pyproject.toml`. Production yêu cầu token dịch vụ riêng. Schema v1 kiểm tra
chặt kiểu của `ticketRevision` ở cả request và response.

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
| Rule-based baseline | Có |
| Real ML/Transformer model | Chưa chọn |
| Embedding port/use case | Scaffold |
| External embedding endpoint | Chưa expose vì backend chưa có canonical contract |
| RAG | Chưa đưa vào MVP |
| Evaluation baseline | Có |

## Chạy local

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

python -m pip install -r requirements-runtime.lock -e ".[dev]"
cp .env.example .env
# Sinh token riêng, sao chép kết quả vào SUPPORTFLOW_AI_SERVICE_TOKEN trong .env:
python -c "import secrets; print(secrets.token_urlsafe(48))"
uvicorn supportflow_ai.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

PowerShell có thể dùng:

```powershell
Copy-Item .env.example .env
```

Endpoint:

```text
POST /v1/ticket-classifications
GET  /health/live
GET  /health/ready
```

Ví dụ request:

```json
{
  "requestId": "00000000-0000-0000-0000-000000000001",
  "ticketId": "00000000-0000-0000-0000-000000000002",
  "ticketRevision": 1,
  "inputHash": "e737e044b7ef976a6f2f2e97f1f2aaee633a2205cc16d051316bf2139d5dc02c",
  "title": "VPN issue",
  "description": "Cisco AnyConnect cannot connect"
}
```

Header:

```text
Authorization: Bearer <SUPPORTFLOW_AI_SERVICE_TOKEN>
```

Rule baseline trả category với `score: null`; nó không giả lập xác suất.

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
