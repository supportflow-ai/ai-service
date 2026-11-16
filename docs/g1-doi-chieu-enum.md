# Đối chiếu enum Impact/Urgency và PriorityMatrix (G1)

Ngày kiểm tra: 2026-11-16. Nguồn: kho `ai-it-service-desk` (Backend), đọc qua `git show` trên các ref dưới đây. Tài liệu này chỉ ghi giá trị đã có trong mã, không phải rubric đã được duyệt.

## Nguồn đã đối chiếu

| Ref Backend | SHA | Ghi chú |
| --- | --- | --- |
| `origin/dev` | `3640c33` | Nhánh tích hợp chuẩn của Backend |
| `origin/main` | `a566fa6` | Kết quả giống `dev` |

File gốc (cùng đường dẫn trên hai ref): `src/backend/Modules/Ticketing/Domain/Impact.cs`, `Urgency.cs`, `PriorityMatrix.cs`.

Hợp đồng v1: SHA-256 của `contracts/ai/v1/openapi.yaml` trên `origin/dev` là `ad1d93230158b9ee66c6e3d0843edafcadde97b01bd2adef62265e4cf7f16428`, khớp `contract.lock.json` của ai-service.

## Enum

| Enum | Giá trị | Khớp hợp đồng v1 |
| --- | --- | --- |
| `Impact` | `Low`, `Medium`, `High` | Có |
| `Urgency` | `Low`, `Medium`, `High` | Có |

## PriorityMatrix (Backend tính, AI không tính)

| Impact \ Urgency | High | Medium | Low |
| --- | --- | --- | --- |
| High | P1 | P2 | P3 |
| Medium | P2 | P3 | P4 |
| Low | P3 | P4 | P4 |

Ma trận này khớp sơ đồ ITIL ghi trong chính file `PriorityMatrix.cs`. Giá trị ngoài enum ném `ArgumentOutOfRangeException`.

## Chưa quyết

- Rubric Impact/Urgency cho AI (mô tả mức độ, tín hiệu, ca mơ hồ) chưa được chủ dự án duyệt. Cho đến khi duyệt, ai-service không gợi ý Impact/Urgency.
- Bảng này không xác nhận việc gán nhãn hay chất lượng mô hình; chỉ xác nhận taxonomy đầu ra.
