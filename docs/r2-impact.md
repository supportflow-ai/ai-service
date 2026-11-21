# Ảnh hưởng của việc chuyển MinIO sang Cloudflare R2 lên ai-service

Trạng thái: **Đã chốt · chờ triển khai**. ADR-017 của Backend được chấp nhận ngày 16/11/2026, áp dụng R2 cho local, kiểm thử, CI, staging và production. Đợt D5 đối chiếu AI Service `b35f08b` và Infra `df08561` ngày 21/11/2026. Compose hiện vẫn có MinIO. Kế hoạch phối hợp nằm ở Backend (`docs/architecture/r2-storage-plan.md`), Web (`docs/architecture/r2-upload-plan.md`) và Infra (`docs/infra/r2-storage-plan.md`).

## Kết luận

Đợt chuyển storage ảnh hưởng đến mô tả môi trường và ca kiểm phối hợp trong CI của AI Service. Runtime, quyền truy cập và hợp đồng của dịch vụ giữ nguyên.

## Căn cứ (đã kiểm tra trong mã)

- Không có phụ thuộc lưu trữ đối tượng: không có `boto`, `minio`, `aws` hay địa chỉ `s3://` trong `src/`, `pyproject.toml`, `requirements-runtime.lock`, `requirements-embeddings.txt`, `Dockerfile` và `.env.example`.
- Dịch vụ không lưu trạng thái và không đọc tệp: phân loại nhận `title`, `description`; chỉ mục tri thức nhận `title`, `content` ngay trong thân yêu cầu `POST /v1/knowledge-indexes:prepare`. Không có đường nào truyền tệp đính kèm hay khóa lưu trữ sang ai-service.
- Biến môi trường của ai-service (`SUPPORTFLOW_AI_*`) không chứa cấu hình lưu trữ.

Mô tả kiểm thử MinIO của Backend trong [hồ sơ kiểm chứng chỉ mục Knowledge](knowledge-index-verification.md) giữ nguyên tại mốc đã kiểm.

## Việc phải làm trong kho này

1. Cập nhật [cẩm nang chung](team-handbook.md) cùng lúc với ba kho còn lại khi giai đoạn 4 của kế hoạch triển khai (nơi cẩm nang nhắc MinIO).
2. Kiểm phần env của service AI và job CI trên ứng viên. Dịch vụ nhận cấu hình AI và Bearer nội bộ qua `SUPPORTFLOW_AI_*`. Endpoint, khóa R2 và quyền bucket thuộc tiến trình Backend thực sự dùng storage.
3. Đối chiếu byte hợp đồng phân loại v1, fixture, `contract.lock.json` và hợp đồng prepare Knowledge với trước khi đổi lưu trữ. Lưu kết quả trên đúng SHA/digest ứng viên.
4. Kiểm `GET /health/live` và `GET /health/ready` của AI Service theo provider đã cấu hình. System và release hiện khai báo classifier `rule`. Mốc này chỉ kiểm dịch vụ AI. Kết quả luồng tệp và nghiệm thu ML có người duyệt được ghi riêng. [Kiến trúc và health AI](architecture.md)
5. Khi phiên bản system/CI/release đã ghim chuyển sang R2 và ca phối hợp đạt, chuyển chỉ dẫn MinIO của phiên bản đó sang lịch sử. Dùng hướng dẫn từng stack tại kho Infra để chạy các phiên bản cũ. Bản phát hành lùi vẫn phải tương thích đồng thời với manifest, API nội bộ và trạng thái dữ liệu do Backend/Infra kiểm.

## Không thuộc phạm vi

Chỉ mục Knowledge cần backend tiêu thụ endpoint `knowledge-indexes:prepare`; việc đó chưa có ở backend và không liên quan đến lưu trữ tệp. Xem [AGENTS.md](../AGENTS.md) mục 6.
