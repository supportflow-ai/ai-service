# Huấn luyện ứng viên phân loại (E1)

Mã trong thư mục này không đóng gói vào image runtime (AGENTS.md mục 1). Trainer dùng chung hàm
`model_input` với provider `ml` (`supportflow_ai.adapters.classifiers.ml.text`), nên huấn luyện và suy
luận không lệch tiền xử lý. Chiều ngược lại không được phép: gói `supportflow_ai` không import `training`.

## Môi trường

Python 3.12, cài như README mục "Chạy local" (có `requirements-ml.txt` cho scikit-learn, joblib, numpy).
Artifact ghi phiên bản thư viện đang chạy; provider từ chối nạp nếu môi trường khác.

## Lệnh

Chạy từ gốc repo:

```sh
python -m training.classifier.train --dataset <thư mục có MANIFEST.json> --out <thư mục artifact trống>
```

| Tham số | Mặc định | Ghi chú |
| --- | --- | --- |
| `--status` | `dev-stub` | `candidate` cần phê duyệt AI-06, ngưỡng AI-07 và cây làm việc sạch |
| `--category-threshold` | `0.0` cho dev-stub | Bắt buộc khi `candidate`. Giá trị 0.0 không bỏ gợi ý nào, chỉ là tạm |
| `--seed` | `20261120` | Cùng seed và cùng dữ liệu cho cùng dự đoán |
| `--artifact-version` | `dev-0` | Theo quy tắc định danh của artifact: chữ thường, số, `.`, `_`, `-` |

Thoát với mã 2 và thông báo `training rejected: <mã>` khi dữ liệu không đạt kiểm tra. Thông báo chỉ là
mã lỗi, không chứa nội dung phiếu.

## Kiểm tra trước khi huấn luyện

- Mọi tệp `.jsonl` trong thư mục phải được liệt kê trong `MANIFEST.json`, và SHA-256 phải khớp. Số mẫu
  (`samples`) cũng phải khớp nếu có.
- Trường quản trị của manifest đều có giá trị không rỗng (xem `evaluation/DATASET.md`).
- Mỗi `split_group_id` thuộc đúng một split. `synthetic` và `public_translated` chỉ ở `train`.
- Category thuộc 11 mã v1. Impact và Urgency nếu có thì là `Low`, `Medium`, `High`.
- Có `train` và `validation`, và `train` có ít nhất hai lớp.
- `candidate` cần `approvalAI06` trong manifest và `--category-threshold`.
- `--out` phải trống.

`test` và `challenge` chỉ được đọc để kiểm rò rỉ nhóm. Trainer không dùng chúng để fit hay chọn
mô hình.

## Huấn luyện và chọn cấu hình

- Đầu vào: `model_input(title, description)` (có bản bỏ dấu).
- Mô hình: `FeatureUnion` (TF-IDF từ và TF-IDF ký tự `char_wb`) rồi `LogisticRegression`.
- Fit trên `train`. Chọn trong lưới 24 cấu hình (n-gram từ, n-gram ký tự, `C`, `class_weight`) theo
  macro-F1 trên `validation`. Khi hòa, lấy cấu hình đứng trước trong lưới.

Lượt này chưa có LinearSVC, OOF theo nhóm, hiệu chuẩn hay chọn ngưỡng. Các phần này thuộc PR-3. Vì
artifact không có khóa `calibration`, provider không phát điểm, và `score` luôn là `null`.

## Đầu ra

- `model.joblib`: pipeline sklearn. Provider nạp qua `joblib.load` trên các byte đã kiểm SHA.
- `manifest.json` schemaVersion 2:
  - `dataset.sha256` là SHA-256 của chính `MANIFEST.json` của dữ liệu. Vì manifest ghi SHA từng tệp,
    hash này khóa toàn bộ dữ liệu.
  - `splitSha256` là SHA-256 của JSON gọn `[[split_group_id, split], ...]` sắp theo nhóm.
  - `evaluation.sealed` luôn là `CHƯA ĐO`. Kết quả test và challenge do bước đánh giá riêng ghi.

Lượt này không ghi cờ bẩn của cây làm việc vào manifest, vì schema v2 không có khóa cho việc đó.
Khi `--status dev-stub` và cây làm việc có thay đổi, trainer chỉ in cảnh báo ra stderr.
