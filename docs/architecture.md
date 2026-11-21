# Kiến trúc AI Service

## Mục tiêu

`ai-service` xử lý suy luận không trạng thái. Mốc đối chiếu ngày 21/11/2026 gồm AI Service `b35f08b`, Backend `dev@3640c33` và Web `dev@89eabc4`. Backend sở hữu dữ liệu và quyền nghiệp vụ.

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

`suggestions` là mảng phần tử `field/value/score` và có tối đa một gợi ý cho mỗi `category`, `impact`, `urgency`. Mảng rỗng thể hiện không có gợi ý. Điểm là số hữu hạn trong [0, 1] hoặc `null`. `rule` chỉ trả một Category với điểm `null`, dùng `OTHER` khi không thấy từ khóa phù hợp. Mức ưu tiên và điều phối thuộc Backend. [OpenAPI và fixture v1](../contracts/ai/v1/README.md)

Xác thực mặc định bật. Chỉ cấu hình `development` và `test` cho phép tắt. Request body được giới hạn ở tầng ASGI, mặc định 64 KiB cho phân loại và cố định 1 MiB cho prepare. [Cấu hình](../src/supportflow_ai/config.py) · [Giới hạn request](../src/supportflow_ai/api/middleware.py)

## Kiểm tra sức khỏe

| Endpoint | Phạm vi kiểm tra |
| --- | --- |
| `GET /health/live` | Tiến trình phản hồi `200` |
| `GET /health/ready` | Phân loại. `rule` trả `200`, `noop` trả `503` |
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
classification: noop | rule
embedding:      noop | local-e5
```

Hai cấu hình độc lập và đều mặc định `noop`. Mô hình phân loại học máy còn chờ chọn và đánh giá theo `AI-07`. Ngày 13/11/2026 chủ dự án chốt inference cục bộ. `AI-02` yêu cầu phân loại có người duyệt cùng Identity và Ticketing trên một ứng viên. [Kế hoạch phân loại](ml-classifier-plan.md) · [Đối chiếu hai dịch vụ](backend-alignment.md)
