# Đối chiếu backend

## Mốc đối chiếu ngày 21/11/2026

AI Service `b35f08b`, Backend `dev@3640c33`, Web `dev@89eabc4` và Infra `df08561`. Mốc Backend cũng đã được đọc ngày 16/11/2026. Mốc mã dùng để đối chiếu, còn kết quả nghiệm thu gắn với cấu hình ứng viên.

| Luồng | Hiện có trong mã | Quyết định hoặc việc còn chờ |
| --- | --- | --- |
| Phân loại phiếu | `POST /v1/ticket-classifications` qua Bearer nội bộ. `rule` trả một Category với `score: null`, mặc định `OTHER` khi không khớp. `noop` trả `503` ở readiness và khi gọi phân loại. Backend có adapter chọn theo `Ai:Enabled`. Web có panel khung với `result={null}` | `AI-02` chốt mô hình học máy cục bộ có người duyệt cùng Identity và Ticketing. Còn thiếu model, caller Ticketing và luồng lưu/duyệt. Tác vụ nền và yêu cầu thủ công sau lưu là hai phương án `AI-03`. Quyền xem và cách biểu diễn triage chờ `AI-01` và `DEC-09` |
| Chuẩn bị chỉ mục | `POST /v1/knowledge-indexes:prepare` nhận snapshot qua Bearer nội bộ. AI Service có `local-e5` và hợp đồng Knowledge riêng. `/health/embedding` kiểm readiness của bộ prepare | Backend sẽ tiêu thụ theo quyết định ngày 13/11. `AI-09` xác định mốc. Chưa có consumer, migration, job, lưu vector hay mốc nguồn cho hợp đồng Knowledge ở Backend |
| Sử dụng Knowledge | Backend/Web có bài viết và tìm kiếm từ khóa | Phạm vi phát hành xét riêng. Truy hồi ngữ nghĩa và RAG thuộc mốc sau phân loại |

OpenAPI phân loại v1 ở hai kho khớp từng byte. SHA-256 là `ad1d93230158b9ee66c6e3d0843edafcadde97b01bd2adef62265e4cf7f16428`, khớp bản ghim. `ticketRevision` là số nguyên không âm. `inputHash` là 64 ký tự hex thường. `suggestions` có tối đa một gợi ý cho mỗi trường và có thể rỗng. Backend kiểm bốn trường tương quan khi nhận phản hồi. Phần ghi kết quả dự kiến dùng `inputHash` để kiểm nội dung và `expectedRevision` để kiểm ghi đồng thời. [OpenAPI v1](../contracts/ai/v1/openapi.yaml) · [Bản ghim](../contract.lock.json)

Backend sở hữu thời hạn chờ, thử lại, ngắt mạch, Priority và quyền áp dụng gợi ý. Phân loại v1 chỉ gợi ý Category, Impact và Urgency. Phiếu `SEC` tiếp tục được phân loại thủ công. Trong bộ checkout liên kho, xem [kế hoạch tích hợp Backend](https://github.com/supportflow-ai/ai-it-service-desk/blob/docs/dong-bo-tai-lieu-2026-11-21/docs/architecture/ai-integration-plan.md) và [hành vi adapter](https://github.com/supportflow-ai/ai-it-service-desk/blob/docs/dong-bo-tai-lieu-2026-11-21/docs/adr/ADR-012-ai-contract-and-future-transport.md#adapter-http-tại-mốc-đối-chiếu). [Enum và PriorityMatrix](g1-doi-chieu-enum.md)

### Đối chiếu phản hồi HTTP phân loại

| Mã HTTP | Bản OpenAPI v1 đã ghim | Runtime ở AI Service `b35f08b` |
| --- | --- | --- |
| `401` | Có phản hồi xác thực dịch vụ | Route kiểm Bearer và từ chối thông tin xác thực thiếu hoặc sai |
| `413` | Chưa khai báo cho route phân loại | Middleware giới hạn payload và trả `detail.code=payload_too_large` |
| `403`, `429` | Có phản hồi cấm truy cập và giới hạn tần suất | Ghi riêng lớp phát mã và xác minh với cấu hình ứng viên trước khi coi đây là phản hồi thực tế của luồng S2S |

OpenAPI còn mô tả mốc thiết kế ban đầu. Dùng byte đã ghim để kiểm schema và fixture. Ghi sai khác HTTP trong ca kiểm runtime và đồng bộ hai kho trong thay đổi hợp đồng có chủ đích. [OpenAPI v1](../contracts/ai/v1/openapi.yaml) · [Bearer](../src/supportflow_ai/api/auth.py) · [Giới hạn payload](../src/supportflow_ai/api/middleware.py)

## Tích hợp S2S tại mốc ngày 05/11/2026

Đối chiếu [AI Service `main@7c09102`](https://github.com/supportflow-ai/ai-service/commit/7c0910298c35150cb28ed2a71605b8c4e03a3938) và [Backend `main@bf38ef9`](https://github.com/supportflow-ai/ai-it-service-desk/commit/bf38ef903f46f6ea21f80da44c11d437391a9efb). Hai bản OpenAPI phân loại v1 khớp từng byte. Backend công bố hợp đồng, AI Service ghim bản sao và checksum. [OpenAPI v1](../contracts/ai/v1/openapi.yaml) · [Bản ghim](../contract.lock.json)

| Thành phần | Trách nhiệm |
| --- | --- |
| Backend | Xây dựng snapshot ticket, tính `inputHash`, gọi qua adapter HTTP khi có luồng nghiệp vụ và đối chiếu phản hồi. Sở hữu quyền, dữ liệu và quyết định thay đổi phiếu |
| AI Service | Nhận `POST /v1/ticket-classifications` qua Bearer riêng giữa các dịch vụ. Kiểm tra định dạng `inputHash`, trả nguyên giá trị cùng các trường định danh và cung cấp gợi ý theo hợp đồng v1 |
| Frontend và hạ tầng | Web giao tiếp với Backend. Hạ tầng giữ AI Service trong mạng nội bộ và quản lý kiểm tra sức khỏe khi triển khai |

Bản chụp này chỉ đối chiếu phân loại v1. Trạng thái hai endpoint và các kiểm tra sức khỏe hiện hành nằm ở [kiến trúc AI Service](architecture.md).

## Mốc xây dựng ban đầu

Code base này được dựng sau khi đọc backend `supportflow-ai/ai-it-service-desk`
nhánh `dev` tại commit:

`e2d1ad406337dbd1a9a63ac6b522b005dc502674`

Các điểm được khóa theo backend:

1. `ITicketClassificationService` chỉ gợi ý Category / Impact / Urgency.
2. `IEmbeddingService` tồn tại nhưng backend hiện vẫn dùng NoOp và chưa có external embedding contract.
3. Contract canonical là `contracts/ai/v1/openapi.yaml`.
4. Category allow-list:
   `ACC NET VPN MAIL SW HW PRINT ACCESS EQUIP SEC OTHER`.
5. Impact / Urgency:
   `Low Medium High`.
6. `requestId`, `ticketId`, `ticketRevision`, `inputHash` phải được echo nguyên trạng.
7. AI không tính Priority và không trả business actions.
8. `SEC` vẫn là manual triage ở backend; AI chỉ được suggest.
9. Service-to-service Bearer là credential riêng, không forward end-user JWT.
10. Backend yêu cầu provider failure phải degrade có kiểm soát và không block ticket flow.
11. CI không phụ thuộc live AI provider.
12. `inputHash` do backend tính; AI service không tự chuẩn hóa/recompute.

## Khoảng trống chưa tự ý lấp

Các mục còn cần quyết định gồm mô hình phân loại và ngưỡng đánh giá, mốc ghim hợp đồng Knowledge từ Backend, truy hồi/RAG và metadata phiên bản model của phản hồi phân loại. `local-e5` đã dùng profile và kích thước vector cụ thể phía AI Service. Bản hợp đồng Knowledge chỉ được ghim khi có nguồn chuẩn để đối chiếu. [Pipeline Knowledge](knowledge-index-pipeline.md)

## Cập nhật 2026-11-13

- Chủ dự án chốt: backend tiêu thụ `POST /v1/knowledge-indexes:prepare`; kế hoạch phía backend ở `docs/architecture/ai-integration-plan.md` của kho `ai-it-service-desk`. Hợp đồng chỉ mục tri thức sẽ chuyển về backend làm bản chuẩn; ai-service giữ bản sao cùng byte.
- Phân loại thật cho MVP chạy bằng mô hình học máy cục bộ, không gọi API bên ngoài: [ml-classifier-plan.md](ml-classifier-plan.md).
