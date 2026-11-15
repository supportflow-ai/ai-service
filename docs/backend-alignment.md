# Đối chiếu backend

## Tích hợp S2S tại mốc ngày 05/11/2026

Đối chiếu [AI Service `main@7c09102`](https://github.com/supportflow-ai/ai-service/commit/7c0910298c35150cb28ed2a71605b8c4e03a3938) và [Backend `main@bf38ef9`](https://github.com/supportflow-ai/ai-it-service-desk/commit/bf38ef903f46f6ea21f80da44c11d437391a9efb). Hai bản OpenAPI phân loại v1 khớp từng byte. Backend công bố hợp đồng, AI Service ghim bản sao và checksum. [OpenAPI v1](../contracts/ai/v1/openapi.yaml) · [Bản ghim](../contract.lock.json)

| Thành phần | Trách nhiệm |
| --- | --- |
| Backend | Xây dựng snapshot ticket, tính `inputHash`, gọi qua adapter HTTP khi có luồng nghiệp vụ và đối chiếu phản hồi. Sở hữu quyền, dữ liệu và quyết định thay đổi phiếu |
| AI Service | Nhận `POST /v1/ticket-classifications` qua Bearer riêng giữa các dịch vụ. Kiểm tra định dạng `inputHash`, trả nguyên giá trị cùng các trường định danh và cung cấp gợi ý theo hợp đồng v1 |
| Frontend và hạ tầng | Web giao tiếp với Backend. Hạ tầng giữ AI Service trong mạng nội bộ và quản lý kiểm tra sức khỏe khi triển khai |

Hai bộ cung cấp hiện có là `rule` và `noop`. Khi dùng `noop`, `/health/ready` trả `503`. Adapter Backend và endpoint phân loại đã có trong mã. Luồng gọi từ Ticketing và lưu quyết định duyệt gợi ý vẫn cần tích hợp đầu cuối. Embedding và RAG cần hợp đồng và quyết định phạm vi riêng. [Điểm vào phân loại](../src/supportflow_ai/api/routes/classification.py) · [Kiểm tra sức khỏe](../src/supportflow_ai/api/routes/health.py)

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

Backend hiện chưa chốt:

- model classification thật;
- embedding model/dimension;
- external embedding HTTP contract;
- RAG/generation contract;
- transport metadata cho provider/model version trong classification response.

Vì vậy base code không tự phát minh các field contract mới.

## Cập nhật 2026-11-13

- Chủ dự án chốt: backend tiêu thụ `POST /v1/knowledge-indexes:prepare`; kế hoạch phía backend ở `docs/architecture/ai-integration-plan.md` của kho `ai-it-service-desk`. Hợp đồng chỉ mục tri thức sẽ chuyển về backend làm bản chuẩn; ai-service giữ bản sao cùng byte.
- Phân loại thật cho MVP chạy bằng mô hình học máy cục bộ, không gọi API bên ngoài: [ml-classifier-plan.md](ml-classifier-plan.md).
