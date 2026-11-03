# Đối chiếu backend

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
