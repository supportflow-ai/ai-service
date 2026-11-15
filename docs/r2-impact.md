# Ảnh hưởng của việc chuyển MinIO sang Cloudflare R2 lên ai-service

Trạng thái: kế hoạch đề xuất chờ chủ dự án duyệt. Cập nhật 2026-11-13, đối chiếu `main` tại `c4669a7`. Quyết định nằm ở ADR-017 của kho backend (`docs/adr/ADR-017-cloudflare-r2-object-storage.md`); kế hoạch các kho khác: backend (`docs/architecture/r2-storage-plan.md`), web (`docs/architecture/r2-upload-plan.md`), infra (`docs/infra/r2-storage-plan.md`).

## Kết luận

**ai-service không phải đổi mã, cấu hình hay hợp đồng** khi hệ thống chuyển lưu trữ tệp từ MinIO sang R2.

## Căn cứ (đã kiểm tra trong mã)

- Không có phụ thuộc lưu trữ đối tượng: không có `boto`, `minio`, `aws` hay địa chỉ `s3://` trong `src/`, `pyproject.toml`, `requirements-runtime.lock`, `requirements-embeddings.txt`, `Dockerfile` và `.env.example`.
- Dịch vụ không lưu trạng thái và không đọc tệp: phân loại nhận `title`, `description`; chỉ mục tri thức nhận `title`, `content` ngay trong thân yêu cầu `POST /v1/knowledge-indexes:prepare`. Không có đường nào truyền tệp đính kèm hay khóa lưu trữ sang ai-service.
- Biến môi trường của ai-service (`SUPPORTFLOW_AI_*`) không chứa cấu hình lưu trữ.

Điểm duy nhất nhắc MinIO là một câu mô tả lần kiểm chứng cũ trong [kiểm chứng chỉ mục Knowledge](knowledge-index-verification.md) (về kiểm thử phía backend của đợt đó); là hồ sơ lịch sử, giữ nguyên.

## Việc phải làm trong kho này

1. Cập nhật [cẩm nang chung](team-handbook.md) cùng lúc với ba kho còn lại khi giai đoạn 4 của kế hoạch triển khai (nơi cẩm nang nhắc MinIO).
2. Không nhận khóa R2: ai-service không cần và **không được** có khóa hay endpoint R2 trong `.env`, Compose hay CI. Nếu sau này có tính năng cần đọc tệp, đó là thay đổi hợp đồng riêng, phải qua backend (kho giữ quyền truy cập dữ liệu và phân quyền), không cho ai-service truy cập trực tiếp bucket.
3. Bàn giao PR của kế hoạch R2 ở các kho khác: xác nhận trong mô tả PR rằng hợp đồng v1 và hợp đồng chỉ mục tri thức không đổi (không cần cập nhật `contract.lock.json`).

## Không thuộc phạm vi

Chỉ mục Knowledge cần backend tiêu thụ endpoint `knowledge-indexes:prepare`; việc đó chưa có ở backend và không liên quan đến lưu trữ tệp. Xem [AGENTS.md](../AGENTS.md) mục 6.
