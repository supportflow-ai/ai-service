# Pipeline lập chỉ mục Knowledge Published

Cập nhật đối chiếu ngày 21/11/2026 tại AI Service `b35f08b` và Backend `dev@3640c33`. AI Service có API prepare, chia khối và embedding CPU. Backend có Knowledge và ảnh chụp khi xuất bản, còn thiếu consumer prepare, migration chỉ mục, job và lưu vector. Phần Backend bên dưới là thiết kế cho mốc `AI-09`. Truy hồi ngữ nghĩa và RAG thuộc mốc riêng.

Hồ sơ TC-346–TC-350 ngày 05/11/2026 mô tả lượt kiểm trên thay đổi local nền `134c9d21287108ff923fffce5ad52a2cb6df3e48`. [Bằng chứng và giới hạn của lượt kiểm đó](knowledge-index-verification.md)

## Trách nhiệm và căn cứ

Backend sở hữu xuất bản, phân quyền và dữ liệu. AI Service nhận snapshot để chia khối, mã hóa và tạo vector. Infra cung cấp runtime PostgreSQL/pgvector và cấu hình image. Thiết kế job giữ bài đã xuất bản khi prepare lỗi. Bảng ghi riêng phần AI đã có và phần Backend cần triển khai.

| Task | Mã chính | Kiểm chứng |
| --- | --- | --- |
| TC-346 | AI có `adapters/markdown_chunker.py` | Markdown block, heading, bảng, code fence, nội dung dài, Unicode, phủ nguồn và tính xác định |
| TC-347 | AI có `domain/knowledge.py` và fixture Knowledge | Hash snapshot/chunk/profile, offset và line. Đối chiếu liên kho khi Backend công bố nguồn chuẩn |
| TC-348 | AI có `adapters/embedders/local_e5.py` | Kiểm dimension, số vector, NaN/Inf và norm |
| TC-349 | Thiết kế Backend `Knowledge/Indexing` và migration `AddKnowledgeIndexPipeline` | Cần kiểm trên PostgreSQL/pgvector, transaction và kích hoạt đúng phiên bản khi triển khai |
| TC-350 | AI có kiểm thử đơn vị và hợp đồng Knowledge. Phần Backend còn chờ | Khi nối Backend, kiểm retry, lease, job trùng/cũ, re-publish, rebuild, archive và rollback |

## 1. Embedding profile

Profile `kb-e5-small-384-v1`, fingerprint `0060fca67682d9d04a273d74df430840b6b367bcc9505bc5cade76268df77bcb`.

- Provider `sentence-transformers-cpu`; model [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), model và tokenizer cùng revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Dimension 384; mean pooling theo cấu hình model; vector L2 normalized. Không gửi nội dung bài viết tới dịch vụ ngoài. Tải model khi build; runtime dùng cache offline, không dùng `trust_remote_code`.
- `markdown-blocks-v1`: ưu tiên ranh giới block Markdown; block quá dài chia theo token. Chunk tối đa mục tiêu 384 token; overlap tối đa 32 token, tối đa 1/4 số token của chunk trước để luôn tiến về phía trước. Giữ nguyên đoạn nguồn, không viết lại code hoặc bảng.
- Input `passage: {title}\n\n{chunk}`. Title tối đa 48 token; toàn input có special tokens tối đa 480, được đếm lại bằng tokenizer thật, không cắt âm thầm.
- `lf-v1`: đổi CRLF/CR thành LF; không NFC, không xóa khoảng trắng trong Markdown. Dữ liệu gốc vẫn nằm trong ArticleVersion của Core.
- Giới hạn v1 gồm nội dung UTF-8 tối đa 131072 byte, 256 chunks và tiêu đề tối đa 200 ký tự. AI trả lỗi khi vượt giới hạn. Theo thiết kế Backend, job chuyển Failed và bài đã xuất bản vẫn được giữ. Ca vượt giới hạn cần xử lý ở khâu soạn bài hoặc thay đổi profile có phiên bản.
- Muốn đổi model/tokenizer/chunker/normalization phải tạo profile mới, đánh giá và migration dimension nếu cần; không sửa nghĩa profile đã lưu. Chưa đánh giá chất lượng truy hồi vì ngoài phạm vi.

## 2. Contract AI–Backend

`POST /v1/knowledge-indexes:prepare` dùng Bearer giữa dịch vụ. AI Service giữ OpenAPI, fixture, profile và manifest cho endpoint này. Theo kế hoạch, Backend sẽ công bố bản chuẩn và AI sẽ ghim bản sao cùng byte. Hiện chưa có commit nguồn ở Backend. `contract.lock.json` đang dùng cho phân loại phiếu v1. [OpenAPI Knowledge](../contracts/ai/knowledge-index/v1/openapi.json) · [Manifest Knowledge](../contracts/ai/knowledge-index/v1/manifest.json)

Request gồm `requestId`, `articleId`, `articleVersionId`, `versionNumber`, `sourceHash`, `profileId`, `title` và `content`. Response trả lại thông tin tương quan và nguồn, kèm `profileHash`, profile đầy đủ, `normalizedContentHash`, khối và vector. Thiết kế Backend dự kiến dùng ID tác vụ làm `requestId` và kiểm tương quan, profile, hash, offset, mức phủ nguồn và vector trước khi lưu.

AI trả `400` cho request, snapshot hoặc profile sai, `401` cho Bearer không hợp lệ, `413` khi body vượt 1 MiB và `503` khi provider chưa sẵn sàng, bận, suy luận lỗi hoặc đầu ra không hợp lệ. Giới hạn đọc phản hồi 8 MiB, thời hạn 60 giây và thử lại 429/5xx/lỗi mạng/hết thời hạn là thiết kế của consumer Backend. Log vận hành chỉ lưu thông tin cần để đối chiếu và chẩn đoán.

## 3. Chunk/source schema

Snapshot source hash là SHA-256 UTF-8 của `byteLength(title):titlebyteLength(content):content`, dùng title/content gốc từ ArticleVersion. Hash chuẩn hóa dùng content sau LF. Hash profile lấy JSON đầy đủ, key sort, separator compact.

Mỗi chunk có index liên tục từ 0, text chính xác từ nguồn đã chuẩn hóa, textHash, headingPath, tokenCount của toàn input, startChar/endChar và startLine/endLine. Offset là chỉ số Unicode scalar, khoảng `[startChar,endChar)`; line bắt đầu từ 1, hai đầu inclusive. Heading trong code fence không trở thành headingPath.

Chunk ID = SHA-256 của `articleVersionId_lowercase\nsourceHash\nprofileHash\nindex\ntextHash`. Rebuild cùng snapshot/profile giữ chunk ID; requestId/indexSetId mới để truy lịch sử lần chạy. Tokenizer/model được ghim giúp tái tạo kết quả; float được kiểm chứng với sai số, không cam kết bit-identical giữa mọi CPU/library.

Thiết kế lưu chỉ mục phía Backend gồm snapshot bất biến, index set gắn phiên bản nguồn và profile, metadata khối và vector 384 chiều. Khóa ngoại liên kết chunk/vector. Khóa cập nhật là `(IndexSetId, ChunkIndex)`. Phạm vi prepare và lưu chỉ mục dừng trước truy vấn ngữ nghĩa.

## 4. Publish/re-publish

**Thiết kế Backend.** Mã hiện hành ghi `ArticleVersion` khi xuất bản lần đầu. Xuất bản lại, tạo job và đổi active index thuộc các bước dưới đây khi triển khai `AI-09`.

Publish lần đầu ghi ArticleVersion V1 và job trong cùng transaction. Re-publish endpoint riêng tạo V2 ngay trong một transaction, giữ snapshot V1, tăng version và tạo job mới. Cùng quyền Agent là tác giả hoặc Admin và kiểm tra xmin hiện có. Hai request cùng revision chỉ một request thành công.

Đây là re-publish trực tiếp; chưa thêm màn hình/workflow sửa nháp V2 kéo dài. Khi publish V2, index V1 mất hiệu lực ngay; không dùng vector V1 thay cho V2 đang pending/failed. Archive ngừng index và loại active pointer, giữ lịch sử. View `knowledge_active_chunks` chỉ gồm current Published version; view không thay thế phân quyền người dùng.

## 5. Worker/index lifecycle

**Thiết kế Backend.** Job, migration lưu vector, lease và view `knowledge_active_chunks` chưa có ở mốc Backend đã đối chiếu.

Core PostgreSQL giữ job bền vững `Pending → Running → Succeeded`, hoặc `Failed`/`Superseded`. Worker claim `FOR UPDATE SKIP LOCKED`, lease token và hạn mặc định 180 giây; tối đa 5 attempts, retry 2^attempt giây, tối đa 60 giây. Worker chết được claim lại sau hết lease; token cũ không được commit.

Completion khóa bài và job, kiểm tra Published + current version + requested job trước khi ghi. Toàn bộ metadata/vector và active pointer commit một transaction; lỗi ở bất kỳ chunk nào rollback tất cả. Publish/archive/rebuild cùng thứ tự khóa. Job cũ không thể kích hoạt sau V2 hoặc sau archive.

Rebuild nhận RequestId do caller tạo; cùng ID và snapshot là replay, không tạo job mới. ID đã dùng cho snapshot khác trả 409. Rebuild tạo index set mới; active set cũ cùng version vẫn dùng được cho tới khi replacement hoàn thành. Sau job Failed, dùng RequestId mới để rebuild. Bài Published có sẵn trước migration cần gọi rebuild, không tự gọi AI khi migrate/startup.

## 6. Chạy và nghiệm thu

### Kiểm tra riêng AI Service

```powershell
.venv/Scripts/python.exe -m pip install -r requirements-runtime.lock -e ".[dev]"
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check .
docker build --target embeddings -t supportflow-ai-knowledge:local .
```

Đặt `SUPPORTFLOW_AI_SERVICE_TOKEN` từ secret store/local environment, ít nhất 32 ký tự; không commit. Chạy image với `SUPPORTFLOW_AI_EMBEDDING_PROVIDER=local-e5`, `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER=rule`, cache `/opt/models`. `/health/embedding` phải 200. `noop` mặc định làm capability indexing trả 503; không sinh vector giả.

Sau khi container đã có cổng localhost:

```powershell
.venv/Scripts/python.exe scripts/smoke_knowledge_index.py --url http://127.0.0.1:8000
```

Script dùng Bearer từ môi trường và dữ liệu giả lập, gọi HTTP hai lần, kiểm số khối, 384 chiều, chuẩn L2, độ phủ và ID khối ổn định. Workflow AI có bước smoke với image embedding. Kiểm thử đơn vị dùng provider giả. Ghi kết quả theo từng lần chạy, SHA và image. [Workflow AI](../.github/workflows/ci.yml)

### Demo tích hợp sau khi có consumer

Trên ứng viên `AI-09`, kiểm publish → Pending → Worker → Succeeded và số khối lớn hơn 0. Kiểm vector 384 chiều gắn đúng `ArticleVersion`. Xuất bản lại V2 giữ snapshot V1 và chỉ kích hoạt V2. Rebuild V2 cùng profile giữ ID khối. Kiểm thêm archive, job cũ hoặc trùng, giới hạn thử lại, sai dimension, rollback và nâng cấp schema cũ. Đây là kế hoạch kiểm chứng. Dùng migration và runbook của ứng viên khi chúng được công bố.
