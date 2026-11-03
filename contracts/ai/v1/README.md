# Hợp đồng AI classification v1

Nguồn chuẩn nằm ở backend `supportflow-ai/ai-it-service-desk`.

AI service **không tự tính lại `inputHash`**. Backend gửi `requestId`, `ticketId`,
`ticketRevision`, `inputHash`, `title`, `description`; AI service phải echo bốn giá trị
correlation nguyên trạng trong response.

Backend hiện dùng thuật toán `ai-input-v2` để tính hash, nhưng chi tiết thuật toán thuộc
quyền sở hữu của backend. AI service chỉ coi hash là opaque correlation value.

Các giá trị contract v1 được khóa:

- Category: `ACC`, `NET`, `VPN`, `MAIL`, `SW`, `HW`, `PRINT`, `ACCESS`, `EQUIP`, `SEC`, `OTHER`.
- Impact/Urgency: `Low`, `Medium`, `High`.
- Tối đa một suggestion cho mỗi field.
- Score là `null` hoặc số hữu hạn trong `[0, 1]`.
- Không có priority, status, assignment, action đặc quyền hoặc dữ liệu workflow trong response.
