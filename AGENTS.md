# AGENTS.md — AI Service (`ai-service`)

Dành cho mọi người làm việc trong kho này, gồm lập trình viên, người kiểm thử, người vận hành và trợ lý AI. Quy tắc chung của cả dự án (quy trình nhánh, commit, PR, giới hạn an toàn, hoàn thành) nằm ở [cẩm nang chung](docs/team-handbook.md). File này chỉ ghi phần riêng của ai-service.

## 0. Đọc trước

**Kho này làm gì.** Dịch vụ FastAPI không lưu trạng thái, cung cấp:

- `POST /v1/ticket-classifications`: gợi ý danh mục, mức ảnh hưởng, độ khẩn cấp cho phiếu theo hợp đồng v1. Provider `rule` (từ khóa) hoặc `noop` (trả 503 có kiểm soát).
- `POST /v1/knowledge-indexes:prepare`: chuẩn bị chỉ mục bài viết Knowledge (chia khối Markdown, embedding CPU E5). Chỉ S2S.
- `GET /health/live`, `/health/ready`, `/health/embedding`.

**Không làm.** Không kết nối database nghiệp vụ; không đổi phiếu, quyền, độ ưu tiên hay luồng xử lý; không gọi model ngoài; chưa có tìm kiếm ngữ nghĩa hay RAG. Backend ([`ai-it-service-desk`](https://github.com/supportflow-ai/ai-it-service-desk)) giữ nghiệp vụ, phân quyền, bước người duyệt, lưu trữ và audit.

Bảy điều cần nhớ trước khi sửa:

1. **Dịch vụ không trạng thái, không DB nghiệp vụ.** Không nhận JWT của người dùng cuối; chỉ nhận Bearer của dịch vụ (S2S).
2. **Xác thực mặc định bật, không có token mặc định.** Thiếu token hợp lệ thì dịch vụ từ chối khởi động; chỉ development và test mới được tắt auth, staging và production không được.
3. **Không ghi log** `title`, `description`, `content`, vector, token hay dữ liệu phiếu.
4. **Hợp đồng v1 thuộc backend.** `contracts/ai/v1/openapi.yaml` phải khớp từng byte với bản của backend; `contract.lock.json` ghim SHA nguồn và hash, CI kiểm tra. Không sửa tay cho lệch.
5. **Ports & Adapters.** Route không gọi SDK model trực tiếp; provider mới đặt trong `adapters/` và đăng ký ở `bootstrap.py`. Kiểm thử `test_architecture_boundaries` canh ranh giới này.
6. **Không giả lập.** Rule baseline trả `score: null`, không bịa xác suất. Schema chặt: từ chối trường lạ, `ticketRevision` phải là số nguyên, body vượt giới hạn trả 413.
7. **Phụ thuộc ML nặng chỉ ở phần embedding**: extra `embeddings` trong `pyproject.toml` và stage `embeddings` của Dockerfile (`requirements-embeddings.txt`). Không thêm chúng vào `requirements-runtime.lock` hay stage `runtime`.

## 1. Cấu trúc

| Đường dẫn | Nội dung |
| --- | --- |
| `src/supportflow_ai/api` | Route, schema, xác thực, middleware, xử lý lỗi |
| `src/supportflow_ai/application` | Use case |
| `src/supportflow_ai/domain` | Kiểu và bất biến nghiệp vụ (ví dụ `ClassificationPrediction`) |
| `src/supportflow_ai/ports`, `adapters` | Cổng và bộ cung cấp: `classifiers/` (`rule_based`, `noop`), `embedders/` (`local_e5`, `noop`), `markdown_chunker` |
| `src/supportflow_ai/bootstrap.py`, `config.py`, `main.py` | Ghép dịch vụ, cấu hình, tạo ứng dụng (`create_app`) |
| `contracts/ai/v1`, `contracts/ai/knowledge-index` | Hợp đồng phân loại v1; hợp đồng chỉ mục tri thức (profile, fixture) |
| `tests/unit`, `integration`, `contract` | Kiểm thử đơn vị, API và hợp đồng |
| `evaluation/` | Baseline đánh giá phân loại; `sample-classification.jsonl` chỉ là dữ liệu smoke, không phải gold set |
| `scripts/` | `validate_ai_contract.py`, `smoke_http.py`, `smoke_knowledge_index.py`, `download_embedding_model.py` |

Tài liệu: [README](README.md), [kiến trúc](docs/architecture.md), [đối chiếu Backend–AI](docs/backend-alignment.md), [pipeline Knowledge](docs/knowledge-index-pipeline.md), [kiểm chứng](docs/knowledge-index-verification.md).

## 2. Lệnh

Cần Python 3.12. Chạy từ gốc repo, trong venv (không cài package vào Python global):

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-runtime.lock -e ".[dev]"
cp .env.example .env     # đặt SUPPORTFLOW_AI_SERVICE_TOKEN riêng, không commit
uvicorn supportflow_ai.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Kiểm tra (đúng các bước của CI):

```sh
ruff check .
pytest
python scripts/validate_ai_contract.py
python -m evaluation.run_classification
python -m compileall -q src evaluation scripts
```

Có thể dùng `make install | lint | test | contract | run | baseline | docker-build`. `make docker-build` tạo image `ghcr.io/supportflow-ai/ai-service:local`; CI chạy thêm bước xác minh HTTP trong container và bước kiểm chứng embedding. Số kiểm thử thực sự chạy phải lớn hơn 0.

## 3. Quy tắc kỹ thuật

- **Thêm provider phân loại:** triển khai `TicketClassifier` trong `adapters/classifiers/`, giữ đầu ra trong `ClassificationPrediction`, đăng ký ở `bootstrap.py`, thêm test hợp đồng và tích hợp, benchmark trên cùng gold set trước khi chọn làm mặc định.
- **Hợp đồng:** schema v1 kiểm chặt kiểu ở cả request và response; phản hồi lặp nguyên `requestId`, `ticketId`, `ticketRevision`, `inputHash`. AI chỉ kiểm định dạng `inputHash`, không tính lại.
- **Bảo mật:** không truyền JWT người dùng, không cấp credential database nghiệp vụ, không trả hành động đặc quyền. Giới hạn body mặc định 64 KiB (`SUPPORTFLOW_AI_MAX_REQUEST_BYTES`, tối đa 1 MiB). Chưa có giới hạn tốc độ phân tán, xoay vòng credential nâng cao hay mTLS; đặt dịch vụ trong mạng riêng, không mở cổng công khai.
- **Dependency:** runtime ghim trong `requirements-runtime.lock`; dependency kiểm thử nằm ở `pyproject.toml`. Không nới ghim để build đạt.
- **Style:** `ruff` (dòng tối đa 100). Không tắt rule để vượt lỗi.

## 4. Ngôn ngữ và Git

Quy ước đầy đủ ở [cẩm nang chung](docs/team-handbook.md). Điểm riêng:

- Tài liệu mới, mô tả commit và PR bằng tiếng Việt có dấu; giữ nguyên định danh, câu lệnh và hợp đồng.
- Tạo nhánh từ `main` và mở PR vào `main`. CI chạy trên mọi push, mọi PR và khi chạy thủ công; job phát hành image lên GHCR chỉ chạy khi dispatch với `publish_images=true`.
- Commit dạng `<loại>(<phạm vi>): <mô tả tiếng Việt>`. **Mã công việc (Jira hoặc công cụ khác) không bắt buộc**; commit cũ có `[TC-<id>]` giữ nguyên.
- Kiểm tra nhánh, HEAD và thay đổi chưa commit trước khi sửa; chỉ đưa phần thuộc nhiệm vụ vào commit, không dùng `git add -A` khi chưa xác minh. Không tự commit khi chỉ được yêu cầu đánh giá hay lập kế hoạch.
- Chỉ sửa AGENTS.md khi nhiệm vụ yêu cầu. Ngoại lệ: đổi lệnh hoặc cấu hình được ghim thì cập nhật hướng dẫn bị ảnh hưởng trong cùng thay đổi.

## 5. Giới hạn an toàn

- Không đưa token, khóa hay dữ liệu thật vào Git, log, fixture hay ảnh chụp. Token dịch vụ sinh riêng (ví dụ `python -c "import secrets; print(secrets.token_urlsafe(48))"`) và đặt trong `.env`, không gửi qua chat.
- Không tự push, hợp nhất PR, phát hành image hay triển khai khi chưa được giao. Không dispatch job phát hành GHCR khi chưa được yêu cầu.
- Không gọi dịch vụ model bên ngoài hay tải model mới ngoài nhiệm vụ; không thay provider mặc định của môi trường chạy thật khi chưa được duyệt.
- Không sửa test, fixture, `contract.lock.json` hay hợp đồng để làm CI xanh.

## 6. Đồng bộ với kho khác

| Bạn đổi | Phải làm |
| --- | --- |
| Hợp đồng phân loại v1 | Chủ sở hữu là **backend**: sửa ở `contracts/ai/v1/openapi.yaml` của backend trước, rồi cập nhật bản sao ở đây và `contract.lock.json` (SHA nguồn, hash) trong cùng đợt |
| Hợp đồng chỉ mục tri thức (`knowledge-indexes:prepare`) | Phối hợp với backend, nơi sẽ tiêu tốn endpoint này. Tại `dev@07ce07a` backend **chưa có** hợp đồng, migration hay mã tiêu thụ; kiểm tra lại trước khi tuyên bố luồng đầu cuối đã chạy |
| Cổng 8000, đường dẫn health, biến môi trường `SUPPORTFLOW_AI_*`, `Dockerfile` | **infra** (Compose dùng `SUPPORTFLOW_AI_SERVICE_TOKEN` lấy từ `AI_S2S_BEARER_TOKEN`) và **backend** (cấu hình `Ai__*`) |
| Phát hành image | Chỉ **infra** ghim digest trong `sources.lock.json`; chỉ nâng khi có quyết định phát hành |

## 7. Kiểm chứng và bàn giao

| Thay đổi | Kiểm tra cần chạy |
| --- | --- |
| Chỉ tài liệu | Đối chiếu liên kết, lệnh và cấu hình; không bắt buộc chạy toàn bộ suite |
| Provider, domain, use case | `ruff check .`, `pytest`, `python -m evaluation.run_classification` |
| Route, schema, hợp đồng, fixture | `pytest` (nhóm `contract` và `integration`) và `python scripts/validate_ai_contract.py` |
| Embedding, chunking, chỉ mục tri thức | Test `test_knowledge_index.py`, `test_knowledge_contract.py`; kiểm chứng embedding thật qua Docker theo CI |
| Dockerfile, dependency, cấu hình | Build image (`make docker-build`) và bước xác minh HTTP trong container như CI |

Gắn kết quả với SHA và thay đổi chưa commit nếu có; không dùng kết quả của commit cũ để xác nhận HEAD mới. Bàn giao ngắn: phạm vi, cách sửa và hợp đồng chịu ảnh hưởng, lệnh cùng số test và kết quả, kiểm tra chưa chạy và lý do, giới hạn, nhánh, SHA và trạng thái push hay PR. CI đạt không tự chứng minh đã nghiệm thu đầy đủ.
