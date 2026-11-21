# Định hướng và kế hoạch AI Service

Định hướng thực nghiệm và tích hợp. Các mục **[cần duyệt]** là đề xuất. Kết quả mô hình trên tập đánh giá tiếng Việt hiện **CHƯA ĐO**.

Đối chiếu ngày 21/11/2026 tại AI Service `b35f08b`, Backend `3640c33`, Web `89eabc4` và Infra `df08561`. Xem [kiến trúc hiện trạng](architecture.md), [đối chiếu Backend](backend-alignment.md), [ma trận Priority](g1-doi-chieu-enum.md) và [quy ước dữ liệu](../evaluation/DATASET.md).

## 0. Tóm tắt

1. **Kiến trúc trong ai-service tốt và nên giữ.** Ports & Adapters rõ ràng, hợp đồng v1 được ghim bằng checksum, schema chặt, không giả lập điểm, không ghi log nội dung phiếu, có kiểm thử ranh giới. Không cần tái cấu trúc lớn. Chỉ cần dọn ít mã thừa và chuẩn bị chỗ cho provider `ml` (mục 4).
2. **Tích hợp vẫn còn thiếu.** Backend đã có adapter HTTP nhưng chưa gọi trong luồng phiếu, chưa lưu `AIAnalysis` và chưa có endpoint duyệt. Panel AI ở Web chưa nối API (mục 3.1).
3. **Dùng `rule` để kiểm thử luồng và quyền.** Chốt thời điểm gọi theo `AI-03`. `AI-02` yêu cầu nghiệm thu Identity, Ticketing và luồng phân loại có người duyệt với mô hình học máy cục bộ trên cùng cấu hình ứng viên.
4. **Dữ liệu chặn đường găng của phần mô hình.** Repo hiện có 11 mẫu smoke. Chuẩn bị tập tiếng Việt và tiêu chí `AI-07` song song với tích hợp.
5. **Truy vết phiên bản mô hình là đề xuất cần duyệt.** Phương án mục 4.3 dùng metadata ngoài body v1.

## 1. Bài toán theo đề xuất của giảng viên

Luồng mục tiêu cho bàn hỗ trợ kỹ thuật tiếng Việt:

```
Người dùng tạo phiếu → Backend lưu → Yêu cầu phân tích theo AI-03
→ AI trả gợi ý → Nhân viên có quyền duyệt → Backend áp dụng, tính Priority và ghi audit
```

| Chức năng | AI Service | Backend |
| --- | --- | --- |
| Phân loại phiếu | Gợi ý 1 trong 11 danh mục: ACC, NET, VPN, MAIL, SW, HW, PRINT, ACCESS, EQUIP, SEC, OTHER | Lưu gợi ý và hiển thị cho người duyệt. SEC qua triage thủ công (`TriagePolicy`) |
| Đánh giá mức độ | Hợp đồng nhận Impact và Urgency (`Low/Medium/High`). Rubric và thời điểm đưa vào gợi ý chờ `AI-05` | Tính Priority P1–P4 theo [ma trận](g1-doi-chieu-enum.md) từ Impact và Urgency của phiếu sau khi áp dụng kết quả duyệt |
| Hỗ trợ định tuyến | Cung cấp Category để Backend tham chiếu | Backend đề xuất SupportTeam theo Category. Người có quyền xác nhận đội trước khi gán Agent. Hai trường hợp chờ là `MANUAL_TRIAGE` khi chưa chọn được đội và đã có đội nhưng chưa có Agent (ADR-016) |

Hợp đồng v1 bao phủ ba trường gợi ý. Ý nghĩa định tuyến của Category phụ thuộc ánh xạ do Backend quản lý. Chỉ đưa Tier vào luật khi bậc xử lý đổi đội nhận hoặc điều kiện chọn người.

AI Service hiện có endpoint `knowledge-indexes:prepare` và embedding E5. Mốc Backend tiêu thụ endpoint thuộc `AI-09`. Phát hành Kho tri thức, tìm kiếm ngữ nghĩa và RAG xét riêng.

## 2. Ràng buộc đã chốt (chủ dự án, 2026-11-13)

1. Mô hình phân loại thật là mục tiêu MVP. Ngày 21/11/2026, `AI-02` xác nhận nghiệm thu cùng Identity và Ticketing, có duyệt đúng quyền và audit.
2. Mô hình **chạy cục bộ**, không gọi API hay dịch vụ model bên ngoài lúc chạy. Dữ liệu phiếu không rời hệ thống.
3. AI chỉ gợi ý. Backend giữ quyền ghi, phân quyền và audit. Người duyệt quyết định cuối.
4. Điểm số phải được hiệu chỉnh hoặc để `null`. `ConfidencePolicy` ở Backend chia Low dưới 0,4, Medium từ 0,4 đến dưới 0,75 và High từ 0,75. `null` chưa có dải. Ngưỡng phát gợi ý là tham số thực nghiệm riêng theo `AI-07`.

## 3. Đánh giá hiện trạng

### 3.1 Kiến trúc hệ thống (bốn kho)

```
Web (React) ──► API Backend (ASP.NET Core, PostgreSQL)
                    └─ adapter HTTP Bearer S2S ──► AI Service (FastAPI)
Luồng Ticketing gọi adapter chưa có. Thời điểm gọi chờ AI-03.
```

| Bước trong luồng | Hiện trạng | Kho |
| --- | --- | --- |
| AI trả gợi ý theo hợp đồng v1 | `rule` luôn trả một Category với `score: null`, dùng `OTHER` khi không khớp. `noop` trả 503. E0 chỉ đo Category | ai-service |
| Adapter gọi AI | **Có**: `HttpTicketClassificationService`, ngắt mạch `ClassificationCircuit` (3 lỗi liên tiếp → mở 30 s), timeout 5 s (1–30) | backend |
| Gọi AI trong luồng phiếu | Chưa có caller Ticketing. Nhân viên yêu cầu phân tích sau khi lưu và chạy nền là hai phương án `AI-03` | backend |
| Lưu `AIAnalysis`/`AISuggestion` | **Chưa**: có domain, chưa có bảng, migration hay `DbSet` | backend |
| Endpoint xem và duyệt triage | **Chưa** | backend |
| Panel AI cho người duyệt | Có component (`AgentReviewPanel`, `WorkspaceTriagePanel`…), **chưa nối API** | web |
| Compose cấu hình ai-service | System/release đặt `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER=rule` và `SUPPORTFLOW_AI_EMBEDDING_PROVIDER=local-e5` | infra |

Ứng viên nghiệm thu cần caller Ticketing, lưu gợi ý, endpoint duyệt, kết nối Web và provider học máy cục bộ. [Đối chiếu luồng tích hợp](backend-alignment.md)

### 3.2 Kiến trúc trong ai-service

```
API (routes, schemas, auth, middleware, errors)
  → Application (ClassifyTicket, PrepareKnowledgeIndex)
    → Ports (TicketClassifier, BatchEmbedder, MarkdownChunker) ← Adapters (rule, noop, local_e5, chunker)
      Domain (Category/Impact/Urgency, Suggestion, ClassificationPrediction)
bootstrap.py, main.py: ghép provider theo cấu hình
```

**Điểm mạnh, giữ nguyên:**

- `test_architecture_boundaries` kiểm ranh giới route và SDK model.
- Bất biến hợp đồng nằm ở domain (`Suggestion`, `ClassificationPrediction`: tối đa 3 gợi ý, mỗi trường 1, điểm hữu hạn trong [0, 1]) và lặp lại ở schema API. Provider sai sẽ bị chặn trước khi tới Backend.
- Hợp đồng v1 ghim theo byte và SHA trong `contract.lock.json`. CI kiểm byte của bản Backend đã ghim. Script `compare_backend_contract.py` dùng để đối chiếu bản Backend ở máy phát triển.
- Bảo mật: auth mặc định bật, token tối thiểu 32 ký tự, giới hạn body ở tầng ASGI, lỗi không lặp lại nội dung phiếu, có kiểm thử log không chứa PII và kiểm thử prompt injection.
- Không giả lập: `rule` trả `score: null`, `noop` trả 503 có kiểm soát.

**Vấn đề và việc cần làm** (mức: **C** cần làm trước khi có `ml`, **N** nên làm, **T** tùy chọn):

| # | Vấn đề (vị trí) | Hệ quả | Việc làm | Mức |
| --- | --- | --- | --- | --- |
| K1 | Cổng `TicketClassifier.classify` là `async`. Suy luận ML tốn CPU | Suy luận trực tiếp trong event loop làm request khác và health phải chờ | Dùng thread và giới hạn song song. Trả 503 có kiểm soát khi vượt giới hạn | C |
| K2 | `bootstrap.py` dựng classifier, còn `main.py` dựng E5 và chunker | Hai luồng có điểm ghép riêng | Đăng ký classifier học máy ở `bootstrap.py`. Chỉ gom phần embedding khi có việc phụ thuộc `AI-09` | N |
| K3 | `GenerateEmbedding`, `TextEmbedder`, `NoOpEmbedder` và `build_classification_use_case` đứng ngoài luồng hiện tại | Cần kiểm điểm tham chiếu trước khi thay đổi | Rà các adapter/cổng cũ trước khi xóa và cập nhật `architecture.md` cùng lúc | N |
| K4 | `/health/ready` chỉ xét tên provider (`noop` → 503) | Provider học máy cần kiểm artifact trước khi nhận yêu cầu | Đề xuất kiểm SHA khi tải và readiness trả 503 nếu artifact lỗi | C |
| K5 | Response, bản phân tích và log hiện thiếu phiên bản mô hình đã ghim | Bằng chứng chạy bóng hay audit cần truy vết đúng artifact | Xem mục 4.3 | C |
| K6 | Giới hạn body ở ASGI của API hiện là 64 KiB theo cấu hình mặc định | Độ dài đầu vào ảnh hưởng độ trễ và dạng đặc trưng | Chốt quy tắc cắt dùng chung khi huấn luyện và suy luận (mục 4.2) | C |
| K7 | Runner hiện dùng `RuleBasedClassifier` và fixture smoke `goldCategory` | Phần so ứng viên cần runner và tập riêng | Đề xuất tham số `--provider`, `--dataset`, `--model-dir` cùng schema thực nghiệm (mục 6.2) | C |
| K8 | Tài liệu kiến trúc đã tách phân loại và Knowledge prepare | Cần giữ cùng mốc với mã khi thêm provider | Cập nhật README và kiến trúc cùng thay đổi runtime | N |
| K9 | Compose cấu hình `local-e5`, Backend chưa tiêu thụ prepare | Cần đo tài nguyên và thời gian khởi động riêng cho embedding | Chính sách provider ở môi trường demo chờ `AI-09` và Infra **[cần duyệt]** | T |
| K10 | Route `knowledge-indexes:prepare` khai báo schema tại route và trả `dict` | Phần chuẩn bị chỉ mục có hợp đồng riêng | Rà khi chốt mốc AI-09 | T |
| K11 | `classifier_provider` mặc định là `noop` và readiness phân loại trả 503 | Môi trường thử smoke cần chủ động chọn `rule` | Dùng cấu hình thử trong README | T |

### 3.3 Cấu trúc thư mục

Đề xuất bổ sung nơi chứa mã huấn luyện, dữ liệu có phiên bản và artifact mô hình vào cấu trúc hiện tại.

```
ai-service/
├─ src/supportflow_ai/
│  ├─ adapters/classifiers/
│  │  ├─ rule_based.py, noop.py                        (hiện có)
│  │  └─ ml/                                            (mới)
│  │     ├─ text.py        chuẩn hóa và cắt văn bản, dùng chung cho huấn luyện và suy luận
│  │     ├─ artifact.py    đọc manifest, kiểm SHA-256, tải mô hình
│  │     └─ tfidf.py | phobert.py   adapter của phương án được chọn
│  └─ bootstrap.py         dựng mọi provider (K2)
├─ training/                                            (mới, không đóng gói vào image)
│  ├─ README.md            cách chạy, môi trường, seed
│  ├─ train_tfidf.py, calibrate.py, export.py
│  └─ requirements-training.txt
├─ evaluation/
│  ├─ data/                                              (mới, có phiên bản)
│  │  ├─ taxonomy-v1.md, guidelines.md                    định nghĩa nhãn, ca biên, ví dụ
│  │  ├─ cards/                                           thẻ kịch bản
│  │  └─ v1/ train.jsonl, dev.jsonl, test.jsonl, challenge.jsonl, MANIFEST.json
│  ├─ metrics.py           + lỗi định tuyến, khớp Priority, ECE
│  ├─ run_classification.py  + tham số provider/dataset/artifact (đề xuất)
│  └─ reports/             báo cáo JSON có SHA mã, phiên bản dữ liệu, phiên bản mô hình
└─ models/                 (gitignore) artifact theo nguồn và SHA ghi trong manifest
```

Nguyên tắc:

- `training/` được import `supportflow_ai.adapters.classifiers.ml.text`, chiều ngược lại thì không. Như vậy huấn luyện và suy luận dùng **cùng một** hàm chuẩn hóa, tránh lệch giữa lúc huấn luyện và lúc chạy.
- Thêm kiểm thử ranh giới: gói `supportflow_ai` không import `training` hay `evaluation`.
- Nơi lưu artifact và quy trình ghim digest do nhóm quyết định **[cần duyệt]**. Dockerfile nhận artifact đã duyệt lúc build và kiểm SHA, theo cách đang dùng với E5.

### 3.4 Đánh giá kế hoạch và hướng đi trước đây

| Điểm | Kế hoạch cũ | Điều chỉnh |
| --- | --- | --- |
| Thứ tự công việc | Tuần tự: dữ liệu → so sánh → adapter → chạy bóng → bật | Ba luồng song song: tích hợp đầu cuối bằng `rule`, dữ liệu, mô hình (mục 9) |
| Phương án mô hình | Đầu phân loại trên E5, TF-IDF, tinh chỉnh transformer | Theo đề xuất của giảng viên: Rule-based, TF-IDF + tuyến tính, PhoBERT. Đầu phân loại trên E5 là phương án phụ |
| Impact/Urgency | "Có thể giữ cách tính hiện có" | E0 hiện chỉ đo Category. Nếu `AI-05` duyệt rubric thì thử Impact/Urgency riêng |
| Truy vết mô hình | Không có | Header phiên bản và cột lưu ở Backend (mục 4.3) |
| Hiệu năng | Chưa nói tới event loop | Suy luận trong thread, giới hạn song song (K1) |
| Điều kiện bàn giao | Chưa nêu | Mốc M1–M5 theo `AI-02` (mục 9) |

## 4. Thiết kế provider `ml`

### 4.1 Hành vi

- Provider dự kiến dùng `title` và `description`, trả tối đa một gợi ý cho mỗi trường. Phương án học máy bắt đầu với Category. Impact/Urgency là thí nghiệm riêng sau khi chốt rubric `AI-05`.
- **Abstain theo từng trường.** Bỏ trường thiếu căn cứ hoặc dưới ngưỡng. Khi bỏ hết, trả `suggestions: []`. Ước lượng ngưỡng trên development theo tiêu chí `AI-07` **[cần duyệt]**. Xuất score đã hiệu chuẩn hoặc `null`.
- `SEC` luôn qua triage thủ công ở Backend. Đo recall và số ca SEC bị bỏ gợi ý. Mọi điều chỉnh ngưỡng theo lớp cần đo trên development trước khi khóa ứng viên.
- Rubric Impact/Urgency theo luật, nếu được duyệt, là một thí nghiệm riêng. Kết quả giữ điểm `null` đến khi có xác suất đã hiệu chuẩn và được kiểm chứng.
- Ghim seed và phiên bản thư viện. Kiểm tính ổn định của đầu ra trên cấu hình đích.

### 4.2 Chuẩn hóa văn bản dùng chung (`ml/text.py`)

1. Ghép `title + "\n" + description`, chuẩn hóa NFC, chuyển chữ thường, gộp khoảng trắng.
2. Đề xuất cắt độ dài một cách xác định, ưu tiên giữ tiêu đề. Ghim giới hạn ký tự của TF-IDF và giới hạn token của checkpoint PhoBERT được thử trong cấu hình thực nghiệm.
3. Với TF-IDF: thêm một bản đã bỏ dấu của cùng văn bản vào đặc trưng n-gram ký tự, để phiếu có dấu và không dấu cùng rơi vào một không gian đặc trưng. Không áp dụng cách này cho rule: với từ khóa đơn, bỏ dấu gây trùng nghĩa ("gặp" thành "gap", "mạng" thành "mang").
4. PhoBERT: tách từ bằng cùng một bộ tách từ ở cả huấn luyện và suy luận.

### 4.3 Truy vết phiên bản mô hình

Backend đọc response bằng `JsonUnmappedMemberHandling.Disallow` và hợp đồng đặt `additionalProperties: false`. Vì vậy **thêm trường vào body sẽ làm Backend lỗi**.

Đề xuất **[cần duyệt cùng Backend]**:

- Nếu được duyệt, ai-service thêm header `X-SupportFlow-Model: <provider>/<model-id>@<version>` vào phản hồi phân loại thành công. Cùng Backend kiểm tương thích transport trước khi ghi header vào tài liệu hợp đồng. Giữ nguyên body v1.
- Backend lưu header vào cột mới `AIAnalysis.ModelVersion` (nullable).
- ai-service ghi `provider` và `model_version` vào log `classification_completed` (`JsonFormatter` đã hỗ trợ khóa `provider`).

### 4.4 Đóng gói và vận hành

- Cấu hình đề xuất gồm `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER=ml`, thư mục artifact và giới hạn chạy song song. Runtime hiện chỉ nhận `noop` và `rule`. Giá trị mới cần mã hỗ trợ và kiểm thử trước khi cập nhật Compose.
- Manifest artifact ghi SHA mã, dataset/split và guideline, preprocess, phiên bản mô hình, phiên bản thư viện, phương pháp hiệu chuẩn, ngưỡng theo trường và digest từng tệp. Khi triển khai, readiness của provider phải kiểm artifact trước khi nhận request.
- Image:
  - Nếu chọn TF-IDF: stage `classifier` dựng từ `runtime`, thêm `scikit-learn` (ghim phiên bản) và artifact. Không đưa vào `requirements-runtime.lock` mặc định (AGENTS.md mục 0, điều 7).
  - Nếu chọn PhoBERT: dựng từ stage `embeddings` (đã có `torch` CPU và `transformers`), thêm bộ tách từ và artifact.
  - Infra chọn target qua Compose. Healthcheck phân loại dùng `/health/ready`.
- Định dạng artifact: tránh pickle khi có thể (ví dụ lưu trọng số và từ vựng TF-IDF sang JSON/NumPy). Nếu buộc dùng `joblib` thì chỉ nạp file đã khớp SHA trong manifest.
- Phương án lùi dự kiến: quay về bản đã ghim dùng `rule` để kiểm thử khói hoặc tắt tính năng ở Backend và tiếp tục triage tay. Kiểm tra đường lùi trên cùng cấu hình ứng viên.

## 5. Ba phương án so sánh

| | E0 · Rule-based | E1 · TF-IDF + tuyến tính | E2 · PhoBERT |
| --- | --- | --- | --- |
| Trạng thái | Đã có để kiểm thử khói, chất lượng trên tập tiếng Việt CHƯA ĐO | Ứng viên học máy đầu tiên, CHƯA ĐO | Nhánh có điều kiện, CHƯA ĐO |
| Cách làm | Từ khóa trả một Category. Ghi riêng số dự đoán `OTHER` | TF-IDF n-gram ký tự và từ, Logistic Regression hoặc LinearSVC. Chọn cấu hình bằng tập phát triển | Đóng băng encoder hoặc tinh chỉnh theo giả thuyết cần thử. Ghim checkpoint, revision và tách từ |
| Tiếng Việt không dấu, viết tắt | Luật dựa trên từ khóa | Dùng n-gram ký tự để thử độ bền | Đo độ bền của checkpoint trên cùng lát challenge |
| Dữ liệu cần | Cùng tập đánh giá Category với E1 | Đủ nhãn và nhóm độc lập để fit, chọn và hiệu chuẩn | Chỉ mở khi có đủ nhãn cho nhóm lỗi cần xử lý |
| Hiệu chuẩn điểm | `null` | Fit bộ hiệu chuẩn bằng phần đã dành trước hoặc dự đoán out-of-fold theo nhóm. Kiểm độ tin cậy trên phần validation | Khóa phương pháp và dùng dữ liệu phát triển như E1 |
| Chạy CPU | p95 và RAM CHƯA ĐO | p95 và RAM CHƯA ĐO | p95 và RAM CHƯA ĐO |
| Huấn luyện | Luật hiện hành | Thử nghiệm trên CPU | Tài nguyên huấn luyện cần được duyệt trước khi bắt đầu |
| Phụ thuộc dự kiến | Provider hiện có | `scikit-learn` khi được duyệt | Checkpoint, tokenizer, bộ tách từ và giấy phép cần đối chiếu |

Mở E2 khi E1 hụt tiêu chí đã duyệt trên development, nhóm chỉ ra được lỗi đáng kể mà biểu diễn ngữ nghĩa có thể giảm, và đủ nhãn, tài nguyên cùng quyền sử dụng checkpoint. Ghi giả thuyết và ngân sách trước khi thử. Nếu E1 đạt tiêu chí trên development, khóa ứng viên E1 để xác nhận trên test/challenge. Quyền đưa dữ liệu ra môi trường khác thuộc `AI-06`.

## 6. Dữ liệu tiếng Việt

### 6.1 Nguồn

Nguồn chính là tình huống tiếng Việt do nhóm chuẩn bị và gán nhãn. Nguồn công khai chỉ vào pipeline sau khi rà quyền sử dụng.

| Nguồn | Vai trò | Ghi chú |
| --- | --- | --- |
| A. Nhóm tự viết theo thẻ kịch bản | Nguồn chính cho phát triển và đánh giá tiếng Việt | Nhóm đánh giá viết độc lập. Có ca có dấu, không dấu, viết tắt, xen tiếng Anh và ca mơ hồ |
| B. Phiếu thật thu được khi thử người dùng | Dữ liệu bổ sung có điều kiện | Dùng theo `AI-06`, rà PII và tách nguồn. Lát đánh giá riêng cần người gán độc lập và phê duyệt |
| C. Nhãn yếu từ phiếu đã đóng | Có thể bổ sung train | Giữ riêng nhãn người gửi và nhãn nhân viên. Chỉ đưa vào train sau khi xác minh nguồn ghi và duyệt quyền sử dụng |
| D. Mẫu dịch hoặc phỏng theo nguồn ngoài | Tham khảo tình huống hoặc bổ sung train | Rà giấy phép, ghi nguồn, biến đổi và `split_group_id` trước khi dùng |

### 6.2 Định dạng dữ liệu thực nghiệm

```json
{"id": "v1-0001", "title": "...", "description": "...",
 "category": "VPN", "impact": "High", "urgency": "High",
 "split_group_id": "VPN-07", "author": "a3", "variant": "khong-dau",
 "source": "A", "split": "train", "notes": ""}
```

- Category giữ 11 mã v1. Trường thiếu căn cứ dùng `null` và cờ `needs-context`. Thống kê nhãn thiếu tách riêng theo trường.
- `author` dùng mã giả. `split_group_id` liên kết nhóm kịch bản, biến thể cùng nguồn và ca gần trùng.
- Dataset thực nghiệm có schema và manifest riêng. Fixture smoke giữ `sample-classification.jsonl` với `goldCategory` và runner hiện hành.

### 6.3 Quy mô và chia tập **[cần duyệt]**

- Pilot xác nhận đủ người gán nhãn và đủ nhóm độc lập. Chốt số mẫu theo lớp/trường ở `AI-07`. Quy mô 100–150 mẫu phát triển mỗi Category, 30 mẫu test mỗi Category là ước lượng của kế hoạch ban đầu, chờ đối chiếu số nhóm và năng lực gán nhãn.
- Gán mỗi nhóm vào đúng một split theo bảng `split_group_id → split`. Cân bằng lớp ở cấp nhóm, rà giao nhau và gần trùng trước khi khóa manifest.
- `train` để fit, tập phát triển để chọn, hiệu chuẩn và chốt ngưỡng. Khóa `test` và `challenge` trước khi chọn model. Chỉ mở sau khi khóa ứng viên, preprocess, calibration, ngưỡng và tiêu chí. Báo riêng test và challenge.

### 6.4 Gán nhãn

Theo [quy ước dữ liệu](../evaluation/DATASET.md), giữ taxonomy và guideline có phiên bản, hai người gán độc lập cho tập đánh giá và người thứ ba phân xử. Báo độ đồng thuận theo trường. Các ca `ACC/ACCESS` và server/hạ tầng `OTHER` chờ `TEAM-03`/`AI-04`. Impact và Urgency dùng rubric hai trục theo `AI-05`. Manifest ghi nguồn, quyền, checksum, rà PII, retention và bản gán split theo `AI-06`.

## 7. Đánh giá và tiêu chí chọn

### 7.1 Chỉ số

| Chỉ số | Trường | Lý do |
| --- | --- | --- |
| Accuracy, Macro-F1, precision/recall/F1, số mẫu từng lớp và confusion matrix | Category. Áp dụng riêng cho Impact/Urgency khi thử theo `AI-05` | Báo số nhãn thiếu và cách tính abstain. Với mẫu có nhãn mà bỏ gợi ý, ghi missed prediction trong báo cáo toàn tập. Ghi riêng dự đoán `OTHER` |
| Recall `SEC` | Category | Báo cả số mẫu `SEC`, số bỏ sót và số ca bỏ gợi ý. Quy tắc triage thủ công giữ nguyên |
| Recall `High` và khớp Priority | Impact, Urgency nếu đã thử | Tính Priority ngoại tuyến qua cùng ma trận Backend khi có đủ hai nhãn thật và hai gợi ý. Ghi tỷ lệ đủ căn cứ |
| Coverage và selective risk theo ngưỡng | Theo từng trường | Coverage = số mẫu có phát gợi ý / số mẫu đánh giá. Selective risk = tỷ lệ sai trong phần đã phát có nhãn tham chiếu. Báo mẫu có nhãn, mẫu bỏ gợi ý và mẫu chuyển xử lý tay |
| ECE và biểu đồ độ tin cậy | Mô hình có score | Đo chất lượng hiệu chuẩn. Báo riêng số mẫu theo dải tin cậy Backend nếu có |
| Độ trễ p50/p95 và RAM đỉnh (RSS) | Provider trên máy đích | Ghi CPU, mức song song, chế độ đo, cold/warm và dữ liệu đo |
| Độ bền | Challenge tách riêng | Đo ca mơ hồ, ít ngữ cảnh, không dấu, viết tắt và xen ngôn ngữ. Giữ biến thể cùng `split_group_id` |

Mỗi báo cáo ghi SHA mã, digest manifest dữ liệu/split, guideline, phiên bản mô hình, thiết bị và số mẫu từng lớp. Nếu dùng khoảng tin cậy, chọn cách tính trước khi mở test và lấy mẫu lại theo nhóm để giữ quan hệ giữa các biến thể. Tỷ lệ lỗi định tuyến chỉ ghi khi có ánh xạ đội đã duyệt. Coverage là tỷ lệ phát gợi ý dùng để đánh giá mô hình, còn việc định tuyến thuộc Backend và người có quyền. Dùng kết quả thử trên phiếu để ghi riêng thời gian triage và tỷ lệ staff sửa hoặc từ chối.

### 7.2 Tiêu chí chọn, chốt trước khi chạy gold set **[cần duyệt]**

1. Fit vectorizer và mô hình trên train. So Logistic Regression và LinearSVC trên validation theo nhóm. Fit hiệu chuẩn và chọn ngưỡng trên các phần development đã dành trước hoặc bằng dự đoán out-of-fold theo nhóm. Chỉ xuất score khi estimator và phương pháp hiệu chuẩn đã được kiểm.
2. Trên development, dùng E0 làm mốc Category. Cổng `AI-07` cần chốt chất lượng tối thiểu, recall `SEC`, quan hệ coverage–risk và ngân sách p95/RSS. Các số dự kiến phải do nhóm duyệt. E2 áp dụng điều kiện ở mục 5.
3. Khóa ứng viên đã chọn, preprocess, hiệu chuẩn, ngưỡng và tiêu chí trước khi mở test/challenge. Chạy E0 và ứng viên đã khóa trên cùng test để xác nhận. Nếu hụt cổng, ghi kết quả và dùng tập đánh giá độc lập chưa mở cho ứng viên mới.
4. Rubric Impact/Urgency, nếu đã duyệt theo `AI-05`, có kết quả riêng. E0 chỉ dùng cho Category. Việc bật mô hình trên ứng viên nghiệm thu còn cần bằng chứng đầu cuối theo `AI-02`.

| Tập đánh giá tiếng Việt | Macro-F1 và chỉ số theo lớp | Recall SEC và coverage–risk | p95/RSS trên máy đích |
| --- | --- | --- | --- |
| E0 | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO |
| E1 | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO |
| E2 nếu đủ điều kiện | CHƯA ĐO | CHƯA ĐO | CHƯA ĐO |

## 8. Việc dọn mã ai-service

Các đề xuất mã bên dưới cần PR và kiểm thử riêng.

| PR | Nội dung | Tương ứng |
| --- | --- | --- |
| Ghép provider | Rà tham chiếu của các adapter/cổng cũ trước khi xóa hoặc gom, sau đó cập nhật kiến trúc | K2, K3, K8 |
| Truy vết | Ghi phiên bản mô hình và header đã duyệt | K5 |
| Readiness | Kiểm artifact hợp lệ khi có provider học máy | K4 |
| Runner | Chọn provider, dataset, manifest và trường cần đo. Giữ đường chạy smoke | K7, mục 7.1 |
| Adapter học máy | Dùng preprocess chung, giữ giới hạn song song và kiểm ranh giới `training`/`evaluation` | K1, K6, mục 4 |

## 9. Lộ trình

Bốn luồng chạy song song. Chưa có lịch học kỳ nên chỉ ghi thứ tự và điều kiện xong, không ghi ngày.

| Luồng | Việc | Kho |
| --- | --- | --- |
| **A. Tích hợp đầu cuối với `rule`** | Sau khi chốt `AI-03`, nối caller, lưu gợi ý, endpoint triage và panel Web. `AI-01` và `DEC-09` định quyền và vòng đời | Backend, Web |
| **B. Dữ liệu** | Taxonomy, guideline, gán nhãn, phân xử, quyền và manifest. Khóa test/challenge | AI Service, nhóm gán nhãn |
| **C. Mô hình** | Chọn E1 trên development, hiệu chuẩn và thử E2 nếu thỏa điều kiện mục 5 | AI Service |
| **D. Adapter và đo** | Công việc mã cần thiết ở mục 8. Truy vết metadata theo thiết kế được duyệt | AI Service, Backend |

| Mốc | Điều kiện xong | Phụ thuộc |
| --- | --- | --- |
| **M0. Quyết định và mốc mã** | Ghi SHA bốn kho, mốc hợp đồng và câu hỏi phải chốt cho lát cắt đầu tiên | Chủ dự án, Backend, Web và AI Service |
| **M1. Kiểm thử tích hợp** | Phiếu được lưu, sau đó Backend gọi `rule` theo trigger đã chốt. Nhân viên có quyền duyệt và Backend ghi audit. Kiểm đường xử lý tay khi AI suy giảm. Priority và đề xuất đội được Backend xử lý sau duyệt theo phạm vi đã mở | Luồng A, `AI-03` |
| **M2. Dữ liệu v1** | Có manifest, thống kê đồng thuận, kiểm rò rỉ giữa tập và test/challenge giữ kín. Dùng development đo E0 | Luồng B, `AI-06` |
| **M3. Chọn và khóa ứng viên** | Có kết quả E1 trên development. Mở E2 chỉ khi đủ điều kiện. Ghim mô hình học máy, preprocess, hiệu chuẩn, ngưỡng và cấu hình máy đích | M2 và cổng `AI-07` |
| **M4. Xác nhận ứng viên** | Mở test/challenge sau khi khóa, báo cáo chỉ số mục 7 và xác nhận ngưỡng cùng cấu hình | M3 |
| **M5. Nghiệm thu chung** | Mô hình học máy cục bộ chạy cùng Identity và Ticketing trên một ứng viên. Có duyệt đúng quyền, audit, xử lý tay khi lỗi và phương án lùi đã kiểm | M1, M4, `AI-02` |

Chạy bóng là thí nghiệm bổ sung khi quyền dữ liệu, tài nguyên và truy vết đã được duyệt.

## 10. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Backend/Web chưa nối luồng lưu và duyệt | Cao | Ưu tiên kiểm thử lát cắt với `rule` khi chốt `AI-03` |
| Dữ liệu tự viết quá đều, điểm cao giả | Cao | Chia theo nhóm, tập đánh giá do người viết độc lập. Lát phiếu thật chỉ bổ sung khi được duyệt `AI-06` |
| Thiếu người gán nhãn thứ hai | Trung bình | Chia chéo trong nhóm để gán đôi toàn bộ tập đánh giá |
| PhoBERT chưa đủ căn cứ hoặc ngân sách | Trung bình | Giữ E1 làm ứng viên nếu đạt tiêu chí. Ghi giả thuyết và quyết định về E2 |
| Bộ tách từ hoặc checkpoint chưa được duyệt | Trung bình | Kiểm tra phiên bản và giấy phép trước khi mở thử nghiệm E2 |
| Suy luận chặn event loop, Backend timeout và mở ngắt mạch | Trung bình | K1: suy luận trong thread, giới hạn song song, đo độ trễ dưới tải |
| Không truy vết được mô hình khi so sánh | Trung bình | Mục 4.3 |

## 11. Quyết định còn mở

1. Quy mô dữ liệu, người gán nhãn, người phân xử và ranh giới Category theo `TEAM-03`/`AI-04` (mục 6).
2. Quyền với từng nguồn, nơi xử lý dữ liệu, quy trình rà PII và thời hạn giữ theo `AI-06`.
3. Rubric Impact/Urgency và mốc áp dụng theo `AI-05`.
4. Tiêu chí, cấu hình máy đích và ngưỡng `AI-07`. Thời điểm gọi, quyền xem và vòng đời triage chờ `AI-03`, `AI-01` và `DEC-09`.
5. Header `X-SupportFlow-Model` và cột `AIAnalysis.ModelVersion` (cần Backend đồng ý).
6. Bộ tách từ cho PhoBERT, giấy phép, có chấp nhận Java trong image không.
7. Nơi lưu artifact mô hình (GitHub Release, volume do infra cấp).
8. Mốc Backend tiêu thụ Knowledge prepare và cấu hình embedding theo `AI-09`.

## 12. Tài liệu phải cập nhật khi triển khai

[Kiến trúc](architecture.md) và [README](../README.md) khi đổi runtime. [Quy ước dữ liệu](../evaluation/DATASET.md) khi khóa dataset và [hướng dẫn làm việc](../AGENTS.md) khi có provider hoặc lệnh mới. Cập nhật tài liệu Backend và Web khi mở API triage hay duyệt metadata phiên bản mô hình. [Đối chiếu Backend](backend-alignment.md)
