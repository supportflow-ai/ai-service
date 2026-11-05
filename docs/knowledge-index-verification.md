# Bằng chứng kiểm chứng Knowledge indexing — 05/11/2026

Phạm vi: TC-346–TC-350, thay đổi local chưa commit/push. Không áp migration vào database ứng dụng hoặc triển khai môi trường dùng chung.

| Repo | Nhánh | HEAD nền |
| --- | --- | --- |
| AI | `feature/TC-348-knowledge-embeddings` | `134c9d21287108ff923fffce5ad52a2cb6df3e48` |
| Core | `feature/TC-220-knowledge-published-index` | `febb4d7ec76dc1a846a554e349981b9b692c7091` |
| Infra | `feature/TC-349-pgvector-runtime` | `77ba2db53c6971adc182a0de60dab607109ed163` |

Các kết quả dưới đây áp dụng cho working tree của phiên triển khai, không phải nguyên HEAD nền và không phải trạng thái CI remote.

## Đã kiểm chứng

- AI: `pytest -o addopts='' -q --disable-warnings`: 78 passed; Ruff, compileall, classification contract validator đạt. Baseline classification 11 mẫu là smoke, không phải đánh giá chất lượng embedding.
- Bốn artifact Knowledge contract giữa Core/AI giống từng byte; Python kiểm manifest/schema/fixture, .NET kiểm tương thích hash/source/Unicode và từ chối output lỗi.
- Core restore `--locked-mode` và build Release: thành công, 0 warning/error. Unit/use-case/architecture/HTTP contract không cần container: 155 + 172 + 26 + 75 = 428 passed. OpenAPI chỉ thêm 3 endpoint và 4 schema Knowledge, không đổi endpoint/schema cũ; test đã chạy lại khi tắt export baseline.
- Core integration: 113 test khác nhau đã passed qua các lượt chạy với PostgreSQL/pgvector Testcontainers. Lượt toàn suite ban đầu 110/111 passed, MinIO timeout khi startup; chạy riêng lại MinIO và 14 test pipeline/processor: 15/15 passed. Không sửa test MinIO để che lỗi. Các test gồm quyền/revision, re-publish cạnh tranh, job cũ, archive, lease/retry, rebuild/replay, transaction rollback và nâng cấp schema cũ.
- Infra: 19 unit/Compose tests passed; local/system Compose config hợp lệ. Windows cần `PYTHONUTF8=1` và `TEST_SH` trỏ Git sh.
- Core image API, Worker, Database build thành công trên Linux Docker local.
- Image AI trước hai sửa cuối đã build thành công; smoke HTTP model E5 thật trả 3 chunks, dimension 384, norm và rebuild ổn định. Container smoke đó đã được dừng/xóa.
- Validator tài liệu Core: 101 tài liệu, 541 liên kết cục bộ đạt. Git diff whitespace kiểm tra đạt.

## Chưa hoàn tất

Sau smoke model thật, đã sửa metadata dòng khi gặp Unicode U+2028/U+2029/U+0085 và xử lý shape output provider sai; 78 test AI bao gồm các hồi quy này. Build lại image AI để xác minh đúng mã cuối bị Docker engine ngắt: `rpc error ... EOF` ở bước tải model. Kiểm tra host lúc đó ổ C chỉ còn khoảng 590 MB. Chưa xác nhận nguyên nhân bằng log engine; cần xử lý dung lượng và phục hồi Docker trước khi thử lại.

Chưa chạy toàn tuyến worker processor → HTTP AI thật → pgvector trên bản cuối. Đã thêm hook smoke localhost trong `WorkerProcessorResolvesWithoutHttpContextAndPersistsOutcome`, build thành công, hướng dẫn trong runbook Core. Test điều phối mặc định dùng provider giả; smoke AI thật và pgvector thật đã kiểm chứng riêng, không coi đó là bằng chứng toàn tuyến dùng model thật.

Không chạy lại build liên tục trên ổ đĩa gần đầy; không tự xóa cache/image/volume của người dùng. Chưa đánh giá SLA hoặc chất lượng semantic retrieval, chưa triển khai RAG. Model/profile/giới hạn là lựa chọn triển khai đề xuất cần review của nhóm. Chưa commit, push, tạo PR hoặc deploy.
