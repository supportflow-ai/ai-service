# Định hướng và kế hoạch AI Service

Trạng thái: định hướng đề xuất, chờ chủ dự án và giảng viên hướng dẫn duyệt các mục đánh dấu **[cần duyệt]**.
Cập nhật 2026-11-17. Đối chiếu mã: ai-service `main@751c8a8` cộng PR #18 (đưa #13, #14 vào `main`); backend `dev@3640c33`; web `dev@89eabc4`; infra `main`.
Tài liệu liên quan: [architecture.md](architecture.md), [g1-doi-chieu-enum.md](g1-doi-chieu-enum.md), [DATASET.md](../evaluation/DATASET.md); phía backend: `docs/architecture/ai-integration-plan.md`, ADR-012, ADR-016.

## 0. Tóm tắt

1. **Kiến trúc trong ai-service tốt và nên giữ.** Ports & Adapters rõ ràng, hợp đồng v1 được ghim bằng checksum, schema chặt, không giả lập điểm, không ghi log nội dung phiếu, có kiểm thử ranh giới. Không cần tái cấu trúc lớn. Chỉ cần dọn ít mã thừa và chuẩn bị chỗ cho provider `ml` (mục 4).
2. **Rủi ro lớn nhất không nằm ở mô hình mà ở tích hợp.** Luồng thầy đề xuất (tạo phiếu → AI gợi ý → người duyệt) **chưa chạy đầu cuối ở đâu cả**. Backend đã có adapter HTTP nhưng chưa gọi trong luồng phiếu, chưa lưu `AIAnalysis`, chưa có endpoint duyệt. Panel AI ở web chưa nối API (mục 3.1).
3. **Định hướng lại: làm lát cắt dọc trước.** Chạy thông luồng đầu cuối bằng provider `rule` hiện có, song song với việc xây dữ liệu. Mô hình thật thay vào sau qua cấu hình mà không đổi hợp đồng. Nhờ vậy dự án luôn có bản demo chạy được, và mô hình được đánh giá trong đúng luồng thật.
4. **Dữ liệu là việc chặn đường găng của phần mô hình.** Chưa có mẫu có nhãn nào ngoài 11 mẫu smoke. Bắt đầu viết dữ liệu ngay, không chờ mã.
5. **Cần truy vết phiên bản mô hình.** Hiện không có cách biết một gợi ý do `rule` hay `ml` phiên bản nào sinh ra, nên không chạy bóng hay audit được. Đề xuất header phản hồi (mục 4.3), không đổi body hợp đồng v1.

## 1. Bài toán theo đề xuất của giảng viên

Service desk kỹ thuật tiếng Việt. Luồng nghiệp vụ:

```
Người dùng tạo phiếu → Backend tiếp nhận → AI phân tích, trả gợi ý
→ Backend tính Priority (PriorityMatrix) và chọn nhóm xử lý (RoutingRule)
→ Agent/Lead/Admin kiểm duyệt, phân công → Xử lý → Đóng phiếu
```

| Chức năng | AI Service | Backend |
| --- | --- | --- |
| Phân loại phiếu | Gợi ý 1 trong 11 danh mục: ACC, NET, VPN, MAIL, SW, HW, PRINT, ACCESS, EQUIP, SEC, OTHER | Lưu gợi ý, hiển thị cho người duyệt; SEC luôn cần triage thủ công (`TriagePolicy`) |
| Đánh giá mức độ | Gợi ý Impact, Urgency (Low/Medium/High) | Tính Priority P1–P4 theo [ma trận](g1-doi-chieu-enum.md); AI không được quyết định Priority (`ForbiddenAIActions.SetFinalPriority`) |
| Hỗ trợ định tuyến | Không làm, chỉ cung cấp Category | `RoutingRule`: `TicketCategory → SupportTeam` (ADR-016) |

AI Service chỉ cần làm tốt ba trường gợi ý và điểm tin cậy. Hợp đồng v1 đã đủ. Lỗi Category nặng nhất là lỗi làm phiếu đi sai nhóm.

Tìm tài liệu liên quan (Knowledge) là P2, ngoài MVP theo tài liệu kiến trúc v3.0 ngày 15/11/2026. Mã `knowledge-indexes:prepare` và embedding E5 giữ nguyên, không phát triển thêm.

## 2. Ràng buộc đã chốt (chủ dự án, 2026-11-13)

1. MVP tích hợp **mô hình phân loại thật**.
2. Mô hình **chạy cục bộ**, không gọi API hay dịch vụ model bên ngoài lúc chạy. Dữ liệu phiếu không rời hệ thống.
3. AI chỉ gợi ý. Backend giữ quyền ghi, phân quyền, audit; người duyệt quyết định cuối.
4. Điểm số phải được hiệu chỉnh hoặc để `null`. Backend chia dải tin cậy (`ConfidencePolicy`): Low dưới 0,4; Medium từ 0,4 đến dưới 0,75; High từ 0,75; `null` thì không có dải.

## 3. Đánh giá hiện trạng

### 3.1 Kiến trúc hệ thống (bốn kho)

```
web (React) ──► backend API (ASP.NET Core, PostgreSQL) ──► ai-service (FastAPI, không trạng thái)
                     │  Worker (tác vụ nền)                     ▲
                     └──────────── Bearer S2S, timeout 5 s ─────┘
infra: Compose (system, release), ghim digest image
```

| Bước trong luồng | Hiện trạng | Kho |
| --- | --- | --- |
| AI trả gợi ý theo hợp đồng v1 | **Có**: `rule` (Category theo từ khóa, Impact/Urgency `High` theo rubric E0, abstain bằng `suggestions: []`) | ai-service |
| Adapter gọi AI | **Có**: `HttpTicketClassificationService`, ngắt mạch `ClassificationCircuit` (3 lỗi liên tiếp → mở 30 s), timeout 5 s (1–30) | backend |
| Gọi AI khi tạo phiếu (tác vụ nền) | **Chưa**: `ClassifyAsync` chỉ được gọi trong kiểm thử | backend |
| Lưu `AIAnalysis`/`AISuggestion` | **Chưa**: có domain, chưa có bảng, migration hay `DbSet` | backend |
| Endpoint xem và duyệt triage | **Chưa** | backend |
| Panel AI cho người duyệt | Có component (`AgentReviewPanel`, `WorkspaceTriagePanel`…), **chưa nối API** | web |
| Compose chạy ai-service | **Có**: `CLASSIFIER_PROVIDER=rule`, `EMBEDDING_PROVIDER=local-e5` | infra |

Kết luận: ai-service đi trước. Đường găng của MVP là backend bước 5–6 trong `ai-integration-plan.md` và phần nối API ở web.

### 3.2 Kiến trúc trong ai-service

```
API (routes, schemas, auth, middleware, errors)
  → Application (ClassifyTicket, PrepareKnowledgeIndex)
    → Ports (TicketClassifier, BatchEmbedder, MarkdownChunker) ← Adapters (rule, noop, local_e5, chunker)
      Domain (Category/Impact/Urgency, Suggestion, ClassificationPrediction; bất biến của hợp đồng)
bootstrap.py, main.py: ghép provider theo cấu hình
```

**Điểm mạnh, giữ nguyên:**

- Ranh giới phụ thuộc đúng hướng; `test_architecture_boundaries` canh route không gọi SDK model.
- Bất biến hợp đồng nằm ở domain (`Suggestion`, `ClassificationPrediction`: tối đa 3 gợi ý, mỗi trường 1, điểm hữu hạn trong [0, 1]) và lặp lại ở schema API. Provider sai sẽ bị chặn trước khi tới Backend.
- Hợp đồng v1 ghim theo byte và SHA (`contract.lock.json`), CI so với bản của Backend; có script đối chiếu `compare_backend_contract.py`.
- Bảo mật: auth mặc định bật, token tối thiểu 32 ký tự, giới hạn body ở tầng ASGI, lỗi không lặp lại nội dung phiếu, có kiểm thử log không chứa PII và kiểm thử prompt injection.
- Không giả lập: `rule` trả `score: null`, `noop` trả 503 có kiểm soát.

**Vấn đề và việc cần làm** (mức: **C** cần làm trước khi có `ml`, **N** nên làm, **T** tùy chọn):

| # | Vấn đề (vị trí) | Hệ quả | Việc làm | Mức |
| --- | --- | --- | --- | --- |
| K1 | `TicketClassifier.classify` là `async`, nhưng suy luận ML tốn CPU (`ports/classifier.py`) | Adapter ML gọi thẳng trong `async def` sẽ chặn event loop; mọi request khác (kể cả health) phải chờ | Adapter `ml` chạy suy luận trong thread (`anyio.to_thread.run_sync`) và giới hạn số lượng song song; vượt giới hạn thì trả 503 có kiểm soát như `embedding_busy` | C |
| K2 | Ghép dịch vụ nằm ở hai nơi: `bootstrap.py` chỉ dựng classifier, còn `main.py` tự dựng E5 và chunker | Thêm provider `ml` sẽ làm `main.py` phình; AGENTS.md lại nói "đăng ký ở `bootstrap.py`" | Chuyển việc dựng embedder và preparer vào `bootstrap.py`; `main.py` chỉ gọi | N |
| K3 | Mã thừa: `application/embedding/service.py` (`GenerateEmbedding`), `ports/embedder.py` (`TextEmbedder`), `adapters/embedders/noop.py`, `bootstrap.build_classification_use_case` | Không nơi nào dùng; gây hiểu nhầm về kiến trúc embedding | Xóa, kèm cập nhật `architecture.md` | N |
| K4 | `/health/ready` chỉ xét tên provider (`noop` → 503) | Với `ml`, tiến trình có thể "ready" khi mô hình tải lỗi hay chưa tải xong | Classifier có thuộc tính `ready`. Tải mô hình lúc khởi động và kiểm SHA; lỗi thì `/health/ready` trả 503 kèm lý do ngắn, không giả lập dự đoán | C |
| K5 | Không truy vết phiên bản mô hình: log `classification_completed` không ghi `provider`; response không có thông tin mô hình; `AIAnalysis` không có cột phiên bản | Không chạy bóng `ml` với `rule` được; không audit được gợi ý do mô hình nào sinh | Xem mục 4.3 | C |
| K6 | `title`, `description` không giới hạn độ dài, chỉ có giới hạn body 64 KiB | PhoBERT nhận tối đa 256 token; TF-IDF chịu được nhưng độ trễ tăng theo độ dài | Cắt văn bản một cách xác định trong mã chuẩn hóa dùng chung (mục 4.2), cùng một hàm cho huấn luyện và suy luận | C |
| K7 | `evaluation/run_classification.py` cố định `RuleBasedClassifier` và file smoke; chỉ đánh giá Category; schema dữ liệu chỉ có `goldCategory` | Không so sánh được ba phương án; không đánh giá được Impact/Urgency | Thêm tham số `--provider`, `--dataset`, `--model-dir`; đánh giá ba trường; mở rộng schema (mục 6.2) | C |
| K8 | `docs/architecture.md` lỗi thời: còn ghi "embedding chưa expose contract", chưa nhắc `knowledge-indexes:prepare`, chưa nhắc Knowledge là P2 | Người mới hiểu sai | Viết lại khi làm K2, K3 | N |
| K9 | Infra chạy `local-e5` ở môi trường demo trong khi Knowledge là P2 | Tốn RAM, khởi động chậm (healthcheck `start-period` 120 s) mà không ai gọi endpoint | Đề xuất với infra: đặt `EMBEDDING_PROVIDER=noop` đến khi mở lại Knowledge **[cần duyệt]** | T |
| K10 | Schema của `knowledge-indexes:prepare` khai báo ngay trong route, trả `dict` không có response model | Không nhất quán với phần phân loại | Để nguyên vì Knowledge đang đóng băng; ghi lại để làm khi mở lại | T |
| K11 | Mặc định `classifier_provider = "noop"`, nên image chạy không cấu hình sẽ báo unhealthy | Đúng chủ ý (không giả lập), nhưng dễ gây bối rối | Ghi rõ trong README và `.env.example`; không đổi mặc định | T |

### 3.3 Cấu trúc thư mục

Cấu trúc hiện tại hợp lý cho một dịch vụ nhỏ. Phần còn thiếu là chỗ cho **mã huấn luyện**, **dữ liệu có phiên bản** và **artifact mô hình**. Đề xuất bổ sung, không di chuyển gì đang có:

```
ai-service/
├─ src/supportflow_ai/
│  ├─ adapters/classifiers/
│  │  ├─ rule_based.py, severity_rules.py, noop.py      (giữ)
│  │  └─ ml/                                            (mới)
│  │     ├─ text.py        chuẩn hóa và cắt văn bản, dùng chung cho huấn luyện và suy luận
│  │     ├─ artifact.py    đọc manifest, kiểm SHA-256, tải mô hình
│  │     └─ tfidf.py | phobert.py   adapter của phương án được chọn
│  └─ bootstrap.py         dựng mọi provider (K2)
├─ training/                                            (mới, không đóng gói vào image)
│  ├─ README.md            cách chạy, môi trường, seed
│  ├─ train_tfidf.py, train_phobert.py, calibrate.py, export.py
│  └─ requirements-training.txt
├─ evaluation/
│  ├─ data/                                              (mới, có phiên bản)
│  │  ├─ taxonomy-v1.md, guidelines.md                    định nghĩa nhãn, ca biên, ví dụ
│  │  ├─ cards/                                           thẻ kịch bản
│  │  └─ v1/ train.jsonl, dev.jsonl, gold.jsonl, MANIFEST.json (SHA từng file, số mẫu từng lớp)
│  ├─ metrics.py           + lỗi định tuyến, khớp Priority, ECE
│  ├─ run_classification.py  + --provider/--dataset/--model-dir, ba trường
│  └─ reports/             báo cáo JSON có SHA mã, phiên bản dữ liệu, phiên bản mô hình
└─ models/                 (gitignore) artifact tải về khi build; nguồn và SHA ghi trong manifest
```

Nguyên tắc:

- `training/` được import `supportflow_ai.adapters.classifiers.ml.text`, chiều ngược lại thì không. Như vậy huấn luyện và suy luận dùng **cùng một** hàm chuẩn hóa, tránh lệch giữa lúc huấn luyện và lúc chạy.
- Thêm kiểm thử ranh giới: gói `supportflow_ai` không import `training` hay `evaluation`.
- Artifact không commit vào Git. TF-IDF chỉ vài MB, PhoBERT vài trăm MB: lưu ở GitHub Release của kho hoặc chỗ do infra cấp **[cần duyệt]**. Dockerfile tải về và kiểm SHA lúc build, giống cách đang làm với E5.

### 3.4 Đánh giá kế hoạch và hướng đi trước đây

| Điểm | Kế hoạch cũ | Điều chỉnh |
| --- | --- | --- |
| Thứ tự công việc | Tuần tự: dữ liệu → so sánh → adapter → chạy bóng → bật | Ba luồng song song: tích hợp đầu cuối bằng `rule`, dữ liệu, mô hình (mục 9) |
| Phương án mô hình | Đầu phân loại trên E5, TF-IDF, tinh chỉnh transformer | Theo đề xuất của giảng viên: Rule-based, TF-IDF + tuyến tính, PhoBERT. Đầu phân loại trên E5 là phương án phụ |
| Impact/Urgency | "Có thể giữ cách tính hiện có" | Đánh giá cả ba trường; Impact/Urgency được giữ rubric E0 nếu mô hình không vượt |
| Truy vết mô hình | Không có | Header phiên bản và cột lưu ở Backend (mục 4.3) |
| Hiệu năng | Chưa nói tới event loop | Suy luận trong thread, giới hạn song song (K1) |
| Định nghĩa xong cho đồ án | Không có | Mốc M1–M5 (mục 9) |

## 4. Thiết kế provider `ml`

### 4.1 Hành vi

- Đầu vào: `title`, `description`. Đầu ra: tối đa một gợi ý cho mỗi trường, kèm điểm đã hiệu chỉnh.
- **Abstain theo từng trường:** xác suất cao nhất dưới ngưỡng của trường đó thì bỏ trường khỏi `suggestions`. Ngưỡng chọn trên tập dev để đạt độ chính xác mục tiêu của các gợi ý được phát ra (ví dụ ≥ 0,9 với Category) **[cần duyệt]**.
- SEC: Backend luôn bắt triage thủ công. Nên đặt ngưỡng SEC thấp hơn để ưu tiên recall, vì bỏ sót sự cố bảo mật đắt hơn báo nhầm.
- Kết hợp với rule (tùy chọn, quyết định sau khi đo): Impact/Urgency có thể lấy từ rubric E0 khi mô hình abstain, nhưng điểm của gợi ý lấy từ rule vẫn là `null`.
- Tính xác định: cùng đầu vào cho cùng đầu ra; cố định seed và phiên bản thư viện.

### 4.2 Chuẩn hóa văn bản dùng chung (`ml/text.py`)

1. Ghép `title + "\n" + description`, chuẩn hóa NFC, chuyển chữ thường, gộp khoảng trắng.
2. Cắt độ dài một cách xác định: TF-IDF tối đa N ký tự; PhoBERT tối đa 256 token, giữ đủ tiêu đề và phần đầu mô tả.
3. Với TF-IDF: thêm một bản đã bỏ dấu của cùng văn bản vào đặc trưng n-gram ký tự, để phiếu có dấu và không dấu cùng rơi vào một không gian đặc trưng. Không áp dụng cách này cho rule: với từ khóa đơn, bỏ dấu gây trùng nghĩa ("gặp" thành "gap", "mạng" thành "mang").
4. PhoBERT: tách từ bằng cùng một bộ tách từ ở cả huấn luyện và suy luận.

### 4.3 Truy vết phiên bản mô hình

Backend đọc response bằng `JsonUnmappedMemberHandling.Disallow` và hợp đồng đặt `additionalProperties: false`. Vì vậy **thêm trường vào body sẽ làm Backend lỗi**.

Đề xuất **[cần duyệt cùng Backend]**:

- ai-service thêm header `X-SupportFlow-Model: <provider>/<model-id>@<version>` (ví dụ `rule/e0@1`, `ml/tfidf-lr@2026.12.1`) vào mọi response phân loại thành công. Header không thuộc schema body nên không vi phạm hợp đồng v1. Ghi lại header này trong phần mô tả của hợp đồng ở Backend.
- Backend lưu header vào cột mới `AIAnalysis.ModelVersion` (nullable).
- ai-service ghi `provider` và `model_version` vào log `classification_completed` (`JsonFormatter` đã hỗ trợ khóa `provider`).

### 4.4 Đóng gói và vận hành

- Cấu hình: `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER=ml`, `SUPPORTFLOW_AI_CLASSIFIER_MODEL_DIR`, `SUPPORTFLOW_AI_CLASSIFIER_MAX_CONCURRENCY`. Thêm `"ml"` vào `Literal` trong `config.py`.
- Manifest artifact: tên, phiên bản, SHA-256 từng file, phiên bản dữ liệu, SHA mã huấn luyện, ngưỡng abstain, tham số hiệu chỉnh. Thiếu file hoặc lệch SHA thì không khởi động được provider và `/health/ready` trả 503.
- Image:
  - Nếu chọn TF-IDF: stage `classifier` dựng từ `runtime`, thêm `scikit-learn` (ghim phiên bản) và artifact. Không đưa vào `requirements-runtime.lock` mặc định (AGENTS.md mục 0, điều 7).
  - Nếu chọn PhoBERT: dựng từ stage `embeddings` (đã có `torch` CPU và `transformers`), thêm bộ tách từ và artifact.
  - Infra chọn target qua Compose; healthcheck vẫn dùng `/health/ready`.
- Định dạng artifact: tránh pickle khi có thể (ví dụ lưu trọng số và từ vựng TF-IDF sang JSON/NumPy). Nếu buộc dùng `joblib` thì chỉ nạp file đã khớp SHA trong manifest.
- Phương án lùi: đổi biến môi trường về `rule`, không cần build lại image.

## 5. Ba phương án so sánh

| | Rule-based | TF-IDF + tuyến tính | PhoBERT |
| --- | --- | --- | --- |
| Trạng thái | Đã có, làm mốc | Cần làm | Cần làm |
| Cách làm | Từ khóa, rubric E0 | n-gram ký tự 2–5 và từ 1–2 (có cả bản bỏ dấu); hồi quy logistic hoặc LinearSVC; mỗi trường một mô hình | Tinh chỉnh `vinai/phobert-base-v2`, ba đầu phân loại trên một encoder hoặc ba mô hình |
| Tiếng Việt không dấu, viết tắt | Phải liệt kê tay | Chịu được nhờ n-gram ký tự | Lệch phân phối pretrain; cần dữ liệu không dấu khi tinh chỉnh |
| Dữ liệu cần | Không | Vài trăm đến một nghìn mẫu là chạy được | Nhiều hơn để vượt TF-IDF rõ rệt |
| Hiệu chỉnh điểm | Không có (`null`) | `CalibratedClassifierCV` (sigmoid hoặc isotonic) trên dev | Temperature scaling trên dev |
| Chạy CPU | Tức thời | Vài ms, mô hình vài MB | Khoảng 135 triệu tham số, vài trăm MB; độ trễ phải đo |
| Huấn luyện | Không | CPU, vài phút | Nên có GPU; CPU có thể mất hàng giờ |
| Phụ thuộc mới | Không | `scikit-learn` | Bộ tách từ (VnCoreNLP cần Java, hoặc thư viện Python); **kiểm tra giấy phép** |

Thứ tự: TF-IDF trước (rẻ, có kết quả sớm), PhoBERT sau. Đầu phân loại trên E5 là phương án phụ, chỉ thêm khi còn thời gian. **Không chọn mô hình trước khi có số liệu.**

Huấn luyện PhoBERT trên dịch vụ GPU bên ngoài (ví dụ Colab) nghĩa là đưa dữ liệu ra ngoài. Dữ liệu tự viết thì không có thông tin cá nhân, nhưng việc này vẫn phải được chủ dự án cho phép **[cần duyệt]**. Ràng buộc mục 2 chỉ nói về lúc chạy dịch vụ.

## 6. Dữ liệu tiếng Việt

### 6.1 Nguồn

Không có bộ phiếu IT tiếng Việt công khai, có nhãn và giấy phép rõ ràng mà dự án dựa vào được.

| Nguồn | Vai trò | Ghi chú |
| --- | --- | --- |
| A. Nhóm tự viết theo **thẻ kịch bản** | Nguồn chính cho huấn luyện và gold set | Thẻ gồm danh mục, Impact, Urgency và tình huống. Bắt buộc đa dạng: có dấu, không dấu, viết tắt ("k vào đc"), xen tiếng Anh, câu cụt, phiếu mơ hồ, phiếu nhiều vấn đề |
| B. Phiếu từ bản demo và buổi thử người dùng | Bổ sung, sát thực tế | Nhãn là danh mục người duyệt chốt; ẩn danh hóa trước khi dùng |
| C. Nhãn yếu từ phiếu đã đóng | Về lâu dài | Cặp danh mục người gửi chọn và nhân viên chốt; cần Backend thêm `RequesterCategoryId`. Không thay gold set |
| D. Phỏng theo bộ ticket công khai tiếng Anh | Tham khảo tình huống | Kiểm tra giấy phép; dịch bằng công cụ bên ngoài phải được cho phép **[cần duyệt]** |

### 6.2 Định dạng (mở rộng `sample-classification.jsonl`)

```json
{"id": "v1-0001", "title": "...", "description": "...",
 "category": "VPN", "impact": "High", "urgency": "High",
 "scenarioId": "VPN-07", "author": "a3", "variant": "khong-dau",
 "source": "A", "split": "train", "notes": ""}
```

- `impact`, `urgency` được để `null` khi người gán không đủ căn cứ. Khi tính chỉ số, mẫu thiếu nhãn thì bỏ qua cho trường đó.
- `author` dùng mã ẩn danh. `scenarioId` và `author` dùng để chia tập theo nhóm.
- Giữ tương thích ngược: runner đọc được `goldCategory` cũ.

### 6.3 Quy mô và chia tập **[cần duyệt]**

- Huấn luyện + dev: khoảng 100–150 mẫu mỗi danh mục (khoảng 1.100–1.650 mẫu), chia 80/20 theo nhóm.
- Gold set: ít nhất 30 mẫu mỗi danh mục (khoảng 330 mẫu), **do người khác viết, từ thẻ kịch bản khác**. Không dùng để chọn siêu tham số hay ngưỡng.
- Chia theo `scenarioId` và `author`, không chia ngẫu nhiên từng câu. Loại câu gần trùng giữa các tập (so độ tương tự n-gram ký tự). Nếu không làm vậy, điểm sẽ cao giả.
- Phân bố Impact/Urgency: bảo đảm mỗi mức có ít nhất 15% số mẫu để mô hình học được cả ba mức.

### 6.4 Gán nhãn

Theo [DATASET.md](../evaluation/DATASET.md): taxonomy có phiên bản; hai người gán độc lập; báo Cohen's kappa cho từng trường; người thứ ba phân xử. Viết `guidelines.md` có ca biên, ví dụ: VPN hay NET; ACC hay ACCESS; HW hay EQUIP; khi nào OTHER.

Rubric Impact/Urgency, bản nháp mở rộng từ E0 **[cần duyệt]**:

| Mức | Impact (phạm vi) | Urgency (mức gấp) |
| --- | --- | --- |
| High | Phòng ban, toàn công ty hoặc dịch vụ dùng chung (mail, VPN, máy chủ) | Bị chặn làm việc **và** (hạn trong ngày hoặc liên quan an toàn thông tin) |
| Medium | Một nhóm vài người | Bị chặn nhưng chưa có hạn gấp, hoặc vẫn làm được với chất lượng giảm |
| Low | Một người | Yêu cầu, hỏi đáp, không chặn công việc |

Dữ liệu nguồn A không chứa thông tin cá nhân thật nên được lưu trong Git ở `evaluation/data/`. Dữ liệu nguồn B, C phải ẩn danh hóa và không đưa vào Git.

## 7. Đánh giá và tiêu chí chọn

### 7.1 Chỉ số

| Chỉ số | Trường | Lý do |
| --- | --- | --- |
| Macro-F1, F1 từng lớp, ma trận nhầm lẫn | Cả ba | Chỉ số chính, theo DATASET.md |
| Tỷ lệ lỗi định tuyến | Category | Nhầm giữa hai danh mục thuộc hai `SupportTeam` khác nhau theo `RoutingRule` (lấy bảng từ dữ liệu seed của Backend) |
| Recall của SEC | Category | Bỏ sót sự cố bảo mật là lỗi đắt nhất |
| Recall mức High | Impact, Urgency | Bỏ sót phiếu khẩn đắt hơn báo nhầm |
| Khớp Priority | Impact + Urgency | Tính P1–P4 từ gợi ý và từ nhãn qua ma trận; báo tỷ lệ khớp đúng và lệch một mức |
| `coverage`, `selectiveAccuracy` theo ngưỡng | Cả ba | Chọn ngưỡng abstain |
| ECE, biểu đồ tin cậy, tỷ lệ mẫu rơi vào từng dải 0,4/0,75 | Mô hình có điểm | Để dải tin cậy của Backend có nghĩa |
| Độ trễ p50/p95 trên CPU, RAM, dung lượng image | Cả ba | "Hiệu năng thực tế" theo yêu cầu |
| Độ bền | Cả ba | Chạy lại gold set ở bản bỏ dấu và bản viết tắt; báo mức giảm Macro-F1 |

Mỗi báo cáo ghi SHA mã, phiên bản dữ liệu (SHA trong `MANIFEST.json`), phiên bản mô hình và số mẫu từng lớp. Nếu gold set có từ 300 mẫu trở lên, báo thêm khoảng tin cậy bootstrap cho Macro-F1, để không kết luận từ chênh lệch nhỏ.

### 7.2 Tiêu chí chọn, chốt trước khi chạy gold set **[cần duyệt]**

1. Mô hình mới chỉ thay `rule` khi vượt `rule` về Macro-F1 Category trên gold set và tỷ lệ lỗi định tuyến không cao hơn.
2. Giữa TF-IDF và PhoBERT: chọn mô hình có Macro-F1 cao hơn; nếu chênh dưới 0,02 hoặc khoảng tin cậy chồng nhau thì chọn mô hình nhẹ hơn.
3. Độ trễ p95 dưới 300 ms trên CPU của máy chạy Compose (Backend chờ tối đa 5 s).
4. ECE dưới 0,1 sau hiệu chỉnh. Không đạt thì trả `score: null` cho trường đó, không trả điểm sai.
5. Impact/Urgency: giữ rubric E0 nếu mô hình không vượt E0 về recall mức High.

## 8. Việc dọn mã ai-service (làm ngay, không phụ thuộc dữ liệu)

Mỗi việc là một PR nhỏ, có kiểm thử:

| PR | Nội dung | Tương ứng |
| --- | --- | --- |
| D1 | Xóa `GenerateEmbedding`, `TextEmbedder`, `NoOpEmbedder`, `build_classification_use_case`; gom việc ghép provider vào `bootstrap.py`; viết lại `architecture.md` | K2, K3, K8 |
| D2 | Log `classification_completed` ghi `provider` và `model_version`; header `X-SupportFlow-Model` (sau khi Backend đồng ý) | K5 |
| D3 | Port classifier có `ready`; `/health/ready` dựa vào `ready` thay vì so tên | K4 |
| D4 | Runner đánh giá: `--provider`, `--dataset`, đủ ba trường, schema mới, `MANIFEST.json`; chỉ số mới ở `metrics.py` | K7, mục 7.1 |
| D5 | Khung `adapters/classifiers/ml/` (`text.py`, `artifact.py`), suy luận trong thread có giới hạn song song; kiểm thử ranh giới `training`/`evaluation` | K1, K6, mục 4 |

## 9. Lộ trình

Bốn luồng chạy song song. Chưa có lịch học kỳ nên chỉ ghi thứ tự và điều kiện xong, không ghi ngày.

| Luồng | Việc | Kho |
| --- | --- | --- |
| **A. Tích hợp đầu cuối với `rule`** | Bước 5 (lưu `AIAnalysis`/`AISuggestion`, tác vụ phân loại nền trong Worker), bước 6 (endpoint xem/duyệt triage), web nối panel AI; thêm `ModelVersion` | backend, web |
| **B. Dữ liệu** | Taxonomy, `guidelines.md`, thẻ kịch bản, viết và gán nhãn, kappa, tách gold set | ai-service (`evaluation/data/`), cả nhóm |
| **C. Mô hình** | TF-IDF, rồi PhoBERT; hiệu chỉnh; báo cáo so sánh | ai-service (`training/`) |
| **D. Dọn mã** | D1–D5 ở mục 8 | ai-service |

| Mốc | Điều kiện xong | Phụ thuộc |
| --- | --- | --- |
| **M0** | PR #18, #19 merge; duyệt các mục **[cần duyệt]** | Chủ dự án, giảng viên |
| **M1. Lát cắt dọc** | Tạo phiếu trên web → Worker gọi ai-service (`rule`) → gợi ý được lưu → Agent thấy và chấp nhận/sửa trên web → Backend tính Priority và nhóm. Chạy được bằng Compose | Luồng A, D1–D3 |
| **M2. Dữ liệu v1** | `evaluation/data/v1` có MANIFEST, kappa, gold set tách riêng; báo cáo mốc của `rule` trên gold set | Luồng B, D4 |
| **M3. TF-IDF** | Báo cáo đủ chỉ số mục 7.1; adapter `ml` chạy trong container; độ trễ đo được | M2, D5 |
| **M4. PhoBERT và chọn mô hình** | Báo cáo so sánh ba phương án; chọn theo tiêu chí mục 7.2; chủ dự án ký | M3 |
| **M5. Bật mô hình** | Chạy bóng (Backend gọi cả `rule` và `ml`, hoặc so trên log có `ModelVersion`) rồi bật `ml` qua cấu hình; có đường lùi về `rule` | M1, M4 |

Nếu thiếu thời gian, thứ tự cắt giảm là: bỏ chạy bóng → bỏ phương án phụ E5 → giữ Impact/Urgency bằng rubric E0. **M1 và M3 là tối thiểu** để có hệ thống chạy được và đáp ứng yêu cầu "mô hình phân loại thật".

## 10. Rủi ro

| Rủi ro | Mức | Giảm thiểu |
| --- | --- | --- |
| Backend/web chưa xong bước 5–6, không có luồng để demo | Cao | Ưu tiên luồng A ngay; ai-service đã sẵn sàng với `rule` |
| Dữ liệu tự viết quá đều, điểm cao giả | Cao | Chia theo nhóm, gold set do người khác viết, bổ sung nguồn B sau buổi thử người dùng |
| Thiếu người gán nhãn thứ hai | Trung bình | Chia chéo trong nhóm; tối thiểu gán đôi toàn bộ gold set |
| PhoBERT không vượt TF-IDF với dữ liệu ít | Trung bình | Kết quả hợp lệ, vẫn báo cáo; chọn TF-IDF theo tiêu chí 7.2 |
| Bộ tách từ cần Java hoặc có giấy phép không phù hợp | Trung bình | Kiểm tra sớm ở M0; dự phòng bằng thư viện Python hoặc không tách từ (ghi rõ trong báo cáo) |
| Suy luận chặn event loop, Backend timeout và mở ngắt mạch | Trung bình | K1: suy luận trong thread, giới hạn song song, đo độ trễ dưới tải |
| Không truy vết được mô hình khi so sánh | Trung bình | Mục 4.3 |

## 11. Quyết định còn mở

1. Quy mô dữ liệu, người viết, người gán nhãn, người phân xử (mục 6).
2. Có cho phép dùng dịch vụ bên ngoài **khi chuẩn bị dữ liệu và huấn luyện** (dịch, GPU đám mây) với dữ liệu không có thông tin cá nhân hay không.
3. Rubric Impact/Urgency mức Low/Medium (mục 6.4).
4. Tiêu chí chọn và ngưỡng (mục 7.2), ngưỡng abstain (mục 4.1).
5. Header `X-SupportFlow-Model` và cột `AIAnalysis.ModelVersion` (cần Backend đồng ý).
6. Bộ tách từ cho PhoBERT, giấy phép, có chấp nhận Java trong image không.
7. Nơi lưu artifact mô hình (GitHub Release, volume do infra cấp).
8. Có tắt `local-e5` ở môi trường demo khi Knowledge còn đóng băng không (K9).

## 12. Tài liệu phải cập nhật khi triển khai

[architecture.md](architecture.md) (D1), [DATASET.md](../evaluation/DATASET.md) (M2), [AGENTS.md](../AGENTS.md) (provider `ml`, thư mục `training/`, lệnh mới), README (bảng trạng thái, chỉ khi mô hình thật đã vào `main`), [cẩm nang chung](team-handbook.md) (bốn kho cùng lúc), `ai-integration-plan.md` của Backend (`ModelVersion`, header).
