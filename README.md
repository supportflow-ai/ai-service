# SupportFlow AI Service

## Pipeline Knowledge Published — 05/11/2026

Đã bổ sung chunking Markdown, metadata nguồn/version, embedding CPU E5 384 chiều và contract S2S indexing cho TC-346–TC-350. Xem [đặc tả sáu phần và hướng dẫn kiểm chứng](docs/knowledge-index-pipeline.md). Core giữ job/worker/pgvector; AI xử lý snapshot được gửi tới. Chưa triển khai semantic query/RAG.

Những lựa chọn profile và giới hạn trong đặc tả là thiết kế triển khai đề xuất để nhóm review. Thay đổi đang ở local; không dùng các mốc lịch sử bên dưới để xác nhận bản phát hành hiện tại.

Xem [kết quả kiểm chứng và bước còn thiếu](docs/knowledge-index-verification.md): test chức năng đã qua; build lại image AI cuối và smoke toàn tuyến model thật còn bị chặn bởi môi trường Docker.

## Cập nhật triển khai 03/11/2026

Code ứng dụng đã có trong working tree `main`, chưa commit/push. Bộ phân loại `rule` là baseline theo luật. Chưa có model học máy được huấn luyện, Outbox backend hoặc luồng Agent duyệt đầu cuối.

`requirements-runtime.lock` ghim các phiên bản runtime đã quan sát trong môi trường kiểm tra; Docker cài từ các phiên bản đó, dùng Uvicorn HTTP cơ bản. Đây là khóa phiên bản, chưa có hash artifact; việc tải đúng các package trên Linux và build image còn chờ CI có mạng/Docker. Dependency kiểm thử hiện vẫn khai báo trong `pyproject.toml`.

Runtime dùng `SUPPORTFLOW_AI_ENVIRONMENT`, `SUPPORTFLOW_AI_SERVICE_TOKEN`, `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER`. Production bắt buộc token; `rule` sẵn sàng còn `noop` trả readiness 503. `ticketRevision` ở request/response là integer nghiêm ngặt; bool, chuỗi, float và số âm bị từ chối. Contract v1 giữ nguyên, không thêm trường modelVersion.

Kiểm tra trong venv: cài `-r requirements-runtime.lock -e ".[dev]"`, chạy Ruff, `scripts/validate_ai_contract.py`, pytest và evaluation theo CI. Máy hiện tại thiếu openapi-spec-validator, DNS tới PyPI bị chặn và vòng lặp asyncio bị kẹt khi Windows tạo socketpair. Chỉ các kiểm thử đồng bộ và lint/compile đã được kiểm chứng local; không đánh dấu HTTP/async/evaluation đạt.

CI có build image không chạy bằng root và healthcheck readiness. Job GHCR chỉ chạy khi dispatch với `publish_images=true` trên main/dev sau quality gates; ghi digest, provenance và SBOM. Chưa phát hành image từ lần sửa này.

Code base cho AI inference service của **SupportFlow AI IT Service Desk**.

Base này được thiết kế từ contract và code backend hiện tại, không biến AI thành một backend
nghiệp vụ thứ hai.

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

python -m pip install -e ".[dev]"
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
```

`evaluation/sample-classification.jsonl` chỉ là smoke data, không phải gold set.

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
