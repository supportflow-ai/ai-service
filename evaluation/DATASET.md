# DATASET

`sample-classification.jsonl` chỉ là dữ liệu smoke-test để kiểm tra pipeline evaluation.
Nó **không phải gold set** và không được dùng làm bằng chứng chất lượng mô hình.

Gold set chính thức cần tuân theo Implementation Specification của backend:

- taxonomy có version;
- quy tắc annotation và boundary/ambiguous cases;
- ít nhất hai thành viên review;
- disagreement được adjudicate;
- gold set không được dùng để tune model/prompt;
- report classification phải có Accuracy, Macro-F1, per-class F1 và confusion matrix.

Kế hoạch dữ liệu (nguồn, quy mô, chia tập, rubric): [ml-classifier-plan.md](../docs/ml-classifier-plan.md) mục 6.

## Định dạng dòng (JSONL)

```json
{"id": "v1-0001", "title": "...", "description": "...",
 "category": "VPN", "impact": "High", "urgency": "High",
 "scenarioId": "VPN-07", "author": "a3", "variant": "khong-dau",
 "source": "A", "split": "gold", "notes": ""}
```

| Trường | Bắt buộc | Ghi chú |
| --- | --- | --- |
| `id` | Có | Duy nhất trong file |
| `title`, `description` | Có | Văn bản phiếu; không chứa thông tin cá nhân thật |
| `category` | Có | Một trong 11 danh mục của hợp đồng v1. Runner vẫn đọc `goldCategory` của dữ liệu smoke cũ |
| `impact`, `urgency` | Không | `Low`/`Medium`/`High` hoặc `null` khi người gán không đủ căn cứ; mẫu `null` bị bỏ qua khi tính chỉ số của trường đó |
| `split` | Không | Lọc bằng `--split` (ví dụ `train`, `dev`, `gold`) |
| `scenarioId`, `author`, `variant`, `source`, `notes` | Không | Dùng khi chia tập theo nhóm và phân tích lỗi; runner không đọc |

Runner từ chối nhãn ngoài taxonomy, `id` trùng và dòng thiếu `category`.

## MANIFEST.json

Nếu thư mục chứa file dữ liệu có `MANIFEST.json`, runner kiểm SHA-256 của file trước khi đánh giá
và dừng khi lệch:

```json
{"version": "v1", "files": {"gold.jsonl": {"sha256": "<hex>", "samples": 330}}}
```

## Chạy đánh giá

```sh
python -m evaluation.run_classification                       # smoke, như CI
python -m evaluation.run_classification --dataset evaluation/data/v1/gold.jsonl --split gold \
    --routing-map evaluation/data/routing-map.json --robustness \
    --output evaluation/reports/rule-gold-v1.json
```

Báo cáo ghi provider, phiên bản mô hình, SHA của dữ liệu và của mã (kèm cờ `dirty`), và trạng thái
bằng chứng (`smoke-only-not-gold`, `manifest-verified`, `unverified-dataset`). Chỉ số cho từng trường:
Accuracy, Macro-F1, F1 từng lớp, ma trận nhầm lẫn, `coverage`, `selectiveAccuracy`, ECE và tỷ lệ
rơi vào dải tin cậy của Backend (khi provider trả điểm), khoảng tin cậy bootstrap của Macro-F1 (từ
300 mẫu). Chỉ số then chốt: Macro-F1 Category, recall SEC, recall mức High của Impact/Urgency, khớp
Priority (qua bản sao PriorityMatrix, chỉ dùng ngoại tuyến), tỷ lệ lỗi định tuyến, độ trễ p50/p95
của lời gọi `classify()` trong tiến trình, và với `--robustness` là mức thay đổi Macro-F1 trên bản bỏ dấu.

`--routing-map` là JSON `{"source": "...", "version": "...", "teams": {"ACC": "<team>", ...}}`
gán nhóm cho đủ 11 danh mục. Backend **chưa có** `RoutingRule` (ADR-016, đợt B2), nên kho này không
kèm bảng mặc định; khi không truyền, báo cáo ghi `"routing": {"status": "not-configured"}`.
