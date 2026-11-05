# Pipeline lập chỉ mục Knowledge Published

Cập nhật 05/11/2026. Phạm vi TC-346–TC-350, thay đổi local trên nền `134c9d21287108ff923fffce5ad52a2cb6df3e48`. Đây là thiết kế đã được hiện thực để review, chưa phải quyết định đã được nhóm phê duyệt. Chưa triển khai semantic query hoặc sinh câu trả lời RAG.

## Trách nhiệm và căn cứ

Yêu cầu nhóm v1.1 (FR-KB-02, FR-KB-06, UC-12) quyết định snapshot, version đang Published và indexing nền không làm mất bài viết khi AI lỗi. Repo Core sở hữu nghiệp vụ publish, phân quyền, snapshot, job và transaction PostgreSQL. AI sở hữu chunking/tokenizer/embedding; Infra sở hữu runtime có pgvector và model. Các giá trị model, giới hạn và retry dưới đây là lựa chọn triển khai đề xuất, cần Leader/Architect review.

| Task | Mã chính | Kiểm chứng |
| --- | --- | --- |
| TC-346 | `adapters/markdown_chunker.py` | Markdown block, heading, bảng, code fence, nội dung dài, Unicode, phủ nguồn và tính xác định |
| TC-347 | `domain/knowledge.py` | Hash snapshot/chunk/profile, offset, line và fixture dùng chung với Core |
| TC-348 | `adapters/embedders/local_e5.py` | Provider CPU thật; từ chối sai dimension, số vector, NaN/Inf và norm |
| TC-349 | Core: `Knowledge/Indexing`, migration `AddKnowledgeIndexPipeline` | PostgreSQL/pgvector thật, transaction và kích hoạt đúng version |
| TC-350 | `tests/unit/test_knowledge_index.py`, `tests/contract/test_knowledge_contract.py`; Core `KnowledgeIndex*Tests` | Retry, lease, job trùng/cũ, re-publish, rebuild, archive, rollback và nâng cấp schema |

## 1. Embedding profile

Profile `kb-e5-small-384-v1`, fingerprint `0060fca67682d9d04a273d74df430840b6b367bcc9505bc5cade76268df77bcb`.

- Provider `sentence-transformers-cpu`; model [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), model và tokenizer cùng revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- Dimension 384; mean pooling theo cấu hình model; vector L2 normalized. Không gửi nội dung bài viết tới dịch vụ ngoài. Tải model khi build; runtime dùng cache offline, không dùng `trust_remote_code`.
- `markdown-blocks-v1`: ưu tiên ranh giới block Markdown; block quá dài chia theo token. Chunk tối đa mục tiêu 384 token; overlap tối đa 32 token, tối đa 1/4 số token của chunk trước để luôn tiến về phía trước. Giữ nguyên đoạn nguồn, không viết lại code hoặc bảng.
- Input `passage: {title}\n\n{chunk}`. Title tối đa 48 token; toàn input có special tokens tối đa 480, được đếm lại bằng tokenizer thật, không cắt âm thầm.
- `lf-v1`: đổi CRLF/CR thành LF; không NFC, không xóa khoảng trắng trong Markdown. Dữ liệu gốc vẫn nằm trong ArticleVersion của Core.
- Giới hạn bản v1: content UTF-8 131072 byte, 256 chunks; title tối đa 200 ký tự theo contract. Quá giới hạn trả lỗi rõ ràng, không index một phần. Core vẫn giữ bài đã publish và báo job Failed. Bài vượt giới hạn cần tách bài hoặc review tăng giới hạn/profile.
- Muốn đổi model/tokenizer/chunker/normalization phải tạo profile mới, đánh giá và migration dimension nếu cần; không sửa nghĩa profile đã lưu. Chưa đánh giá chất lượng truy hồi vì ngoài phạm vi.

## 2. Contract AI–Backend

`POST /v1/knowledge-indexes:prepare`, chỉ S2S `Authorization: Bearer`. Hợp đồng `contracts/ai/knowledge-index/v1/openapi.json`; fixture, profile và manifest nằm cùng thư mục. Bản chuẩn do Core sở hữu; AI giữ bản sao cùng byte. Đây là contract mới chưa có commit upstream để ghim; không thay `contract.lock.json` của classification bằng SHA giả.

Request gồm `requestId` (job ID), `articleId`, `articleVersionId`, `versionNumber`, `sourceHash`, `profileId`, `title`, `content`. Response lặp toàn bộ correlation/source identifiers; thêm `profileHash`, profile đầy đủ, `normalizedContentHash` và chunks/vector. Core kiểm tra lại toàn bộ tương quan, profile, hash, offset/source coverage và vector trước khi lưu.

400: request/snapshot/profile không hợp lệ; 401: S2S; 413: body quá lớn; 503: provider chưa bật, bận, lỗi inference hoặc output không hợp lệ. Request tối đa 1 MiB; Core chỉ đọc response tối đa 8 MiB. Timeout Core 60 giây. Core retry 429/5xx/network/timeout; lỗi contract hoặc 4xx khác là lỗi cuối cùng. Không ghi body nội dung/vector, token hoặc phản hồi lỗi thô vào log.

## 3. Chunk/source schema

Snapshot source hash là SHA-256 UTF-8 của `byteLength(title):titlebyteLength(content):content`, dùng title/content gốc từ ArticleVersion. Hash chuẩn hóa dùng content sau LF. Hash profile lấy JSON đầy đủ, key sort, separator compact.

Mỗi chunk có index liên tục từ 0, text chính xác từ nguồn đã chuẩn hóa, textHash, headingPath, tokenCount của toàn input, startChar/endChar và startLine/endLine. Offset là chỉ số Unicode scalar, khoảng `[startChar,endChar)`; line bắt đầu từ 1, hai đầu inclusive. Heading trong code fence không trở thành headingPath.

Chunk ID = SHA-256 của `articleVersionId_lowercase\nsourceHash\nprofileHash\nindex\ntextHash`. Rebuild cùng snapshot/profile giữ chunk ID; requestId/indexSetId mới để truy lịch sử lần chạy. Tokenizer/model được ghim giúp tái tạo kết quả; float được kiểm chứng với sai số, không cam kết bit-identical giữa mọi CPU/library.

Core lưu snapshot bất biến, index set với version/source/profile JSON và fingerprint, chunk metadata và bảng vector(384). Foreign key liên kết chunk/vector; upsert vector theo `(IndexSetId, ChunkIndex)`. Không thêm ANN index hoặc truy vấn semantic.

## 4. Publish/re-publish

Publish lần đầu ghi ArticleVersion V1 và job trong cùng transaction. Re-publish endpoint riêng tạo V2 ngay trong một transaction, giữ snapshot V1, tăng version và tạo job mới. Cùng quyền Agent là tác giả hoặc Admin và kiểm tra xmin hiện có. Hai request cùng revision chỉ một request thành công.

Đây là re-publish trực tiếp; chưa thêm màn hình/workflow sửa nháp V2 kéo dài. Khi publish V2, index V1 mất hiệu lực ngay; không dùng vector V1 thay cho V2 đang pending/failed. Archive ngừng index và loại active pointer, giữ lịch sử. View `knowledge_active_chunks` chỉ gồm current Published version; view không thay thế phân quyền người dùng.

## 5. Worker/index lifecycle

Core PostgreSQL giữ job bền vững `Pending → Running → Succeeded`, hoặc `Failed`/`Superseded`. Worker claim `FOR UPDATE SKIP LOCKED`, lease token và hạn mặc định 180 giây; tối đa 5 attempts, retry 2^attempt giây, tối đa 60 giây. Worker chết được claim lại sau hết lease; token cũ không được commit.

Completion khóa bài và job, kiểm tra Published + current version + requested job trước khi ghi. Toàn bộ metadata/vector và active pointer commit một transaction; lỗi ở bất kỳ chunk nào rollback tất cả. Publish/archive/rebuild cùng thứ tự khóa. Job cũ không thể kích hoạt sau V2 hoặc sau archive.

Rebuild nhận RequestId do caller tạo; cùng ID và snapshot là replay, không tạo job mới. ID đã dùng cho snapshot khác trả 409. Rebuild tạo index set mới; active set cũ cùng version vẫn dùng được cho tới khi replacement hoàn thành. Sau job Failed, dùng RequestId mới để rebuild. Bài Published có sẵn trước migration cần gọi rebuild, không tự gọi AI khi migrate/startup.

## 6. Chạy và nghiệm thu

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

Script dùng cùng token trong environment và dữ liệu giả lập, gọi HTTP hai lần, kiểm tra nhiều chunks, 384 chiều, L2, coverage và rebuild ổn định. CI chạy smoke bằng image thực. Unit tests dùng provider giả chỉ để ép nhánh lỗi; không lấy chúng làm bằng chứng model thật.

Demo tích hợp: publish → GET trạng thái Pending → worker → Succeeded + chunkCount > 0; query SQL kiểm vector_dims=384 và đúng ArticleVersion. Re-publish V2, giữ V1 snapshot nhưng active chỉ V2. Rebuild V2 cùng profile giữ chunk IDs. Kiểm thử thêm archive, worker cũ/trùng, retry, hết attempts, sai dimension, rollback giữa chừng và migration từ schema cũ. Lệnh migration, API và SQL chi tiết nằm trong runbook Knowledge của Core; không tự migrate database đang dùng.
