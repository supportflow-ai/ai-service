# DATASET

> Phần taxonomy và hướng dẫn gán nhãn mô tả dữ liệu đánh giá. Phần cuối ghi định dạng và cách chạy runner tại `main@09ca691`. Runner hiện yêu cầu nhãn Category hợp lệ với các dòng đưa vào đánh giá. Giữ riêng ca thiếu căn cứ theo hướng dẫn gán nhãn bên dưới.

`sample-classification.jsonl` gồm 11 mẫu kiểm thử khói cho runner Category hiện tại. Giữ nguyên trường `goldCategory` của fixture. Kết quả từ tệp này chỉ xác nhận đường chạy. Chất lượng mô hình chờ tập đánh giá tiếng Việt và tiêu chí `AI-07`.

## Taxonomy và hướng dẫn gán nhãn

Giữ 11 mã Category v1: `ACC`, `NET`, `VPN`, `MAIL`, `SW`, `HW`, `PRINT`, `ACCESS`, `EQUIP`, `SEC`, `OTHER`. `OTHER` là mã hợp lệ cho ca đã hiểu rõ nhưng nằm ngoài các nhóm còn lại. Ghi `null` và cờ `needs-context` ở trường thiếu căn cứ. Khi trả API v1, bỏ trường không có gợi ý. `unknown`, top-k và cờ gán nhãn chỉ dùng ngoại tuyến. `SEC` tiếp tục qua triage thủ công. [Hợp đồng v1](../contracts/ai/v1/openapi.yaml) · [Đối chiếu Backend](../docs/backend-alignment.md)

| Ca thử guideline | Nhãn dự kiến theo mã hiện có | Điều kiện áp dụng |
| --- | --- | --- |
| Quên mật khẩu tài khoản công ty | `ACC` | Nhu cầu khôi phục tài khoản. Nếu có tín hiệu tài khoản bị chiếm, xét `SEC` và triage thủ công |
| Xin quyền thư mục dùng chung | `ACC` | Quyền hệ thống số theo định nghĩa v1. Nếu nguyên nhân thực tế là kết nối mạng, xét `NET` hoặc `VPN` theo nội dung |
| Thẻ ra vào không mở cửa | `ACCESS` | Truy cập vật lý. Tên hiển thị trên Web có nghĩa rộng hơn nên cần xác nhận ranh giới ở `TEAM-03` |
| Dịch vụ máy chủ ngừng vì lỗi hạ tầng đã xác nhận | `OTHER` | Đề xuất cho ca nằm ngoài các mã v1 theo `AI-04`. Có thể ghi `infra_domain=server` ngoại tuyến. Dùng `NET` nếu vấn đề chính là kết nối, `SW` nếu vấn đề chính thuộc ứng dụng |

Các ca trên dùng để thử độ nhất quán của guideline. Ánh xạ Category sang SupportTeam chờ `TEAM-03`. Bộ mã v1 giữ nguyên trong lúc xét ca hạ tầng với `AI-04`.

Rubric dưới đây là đề xuất `AI-05`. Gán Impact và Urgency độc lập, kèm chi tiết trong phiếu làm căn cứ. Thiếu chi tiết ở trục nào thì để trống nhãn trục đó. Priority do Backend tính bằng ma trận.

| Mức | Impact · phạm vi và mức gián đoạn | Urgency · thời gian có thể chờ |
| --- | --- | --- |
| `Low` | Gián đoạn nhẹ hoặc giới hạn ở một cá nhân | Có thể lên lịch vì công việc vẫn tiếp tục ổn định |
| `Medium` | Nhóm người dùng hoặc quy trình bị giảm khả năng làm việc | Cần xử lý sớm để duy trì công việc. Giải pháp tạm chỉ đáp ứng một phần hoặc chưa có hạn ngay |
| `High` | Gián đoạn nghiêm trọng đối với nhiều người, phòng ban hoặc dịch vụ thiết yếu | Cần xử lý ngay vì hạn gần, hậu quả tăng nhanh hoặc có tín hiệu rủi ro an toàn |

Ví dụ “cả phòng không dùng được hệ thống” cho biết phạm vi Impact. Chỉ gán Urgency khi có thêm căn cứ về hạn xử lý, mức gián đoạn hoặc cách làm tạm. Hai người gán độc lập các trường của tập đánh giá, người thứ ba phân xử bất đồng. Lưu phiên bản taxonomy/guideline, kết quả phân xử và độ đồng thuận theo từng trường.

## Nguồn, quyền và thời hạn giữ

- Bắt đầu với tình huống do người viết và mã giả. Tách người viết tập đánh giá tiếng Việt khỏi người viết dữ liệu phát triển. Bản dịch, biến thể tổng hợp hoặc dữ liệu công khai đã rà nguồn chỉ dùng bổ sung train.
- `AI-06` chờ chủ dữ liệu duyệt trước khi dùng phiếu thật. Phê duyệt ghi mục đích, người được truy cập, nơi xử lý, thời hạn giữ và cách xóa riêng cho phiếu thô, dataset đã rà, gợi ý và bản ghi duyệt. Rà PII bằng công cụ rồi kiểm thủ công tên riêng, thông tin liên hệ, mã nội bộ và thông tin nhạy cảm. Dữ liệu thật và bản thô ở kho hạn chế quyền ngoài Git.
- Giữ riêng nhãn người gửi, gợi ý của AI, nhãn nhân viên chốt và nhãn gold do người gán. Đầu vào mô hình v1 là tiêu đề và mô tả. Nhãn, đội nhận, bình luận sau xử lý và metadata khác phục vụ phân tích ngoại tuyến.
- `MANIFEST.json` cần phiên bản tập dữ liệu và guideline, nguồn/phiên bản nguồn, giấy phép hoặc phê duyệt, biến đổi khi dịch hoặc gán lại nhãn, kết quả rà PII, quy tắc giữ/xóa, SHA-256 từng tệp và thống kê theo nguồn, nhóm, split và lớp. Dẫn bảng `split_group_id → split` cùng checksum.

## Chia tập và mở đánh giá

Lập một bảng gán duy nhất cho cả nhóm kịch bản, biến thể cùng nguồn và ca gần trùng. Mỗi `split_group_id` thuộc đúng một split. Cân bằng lớp ở cấp nhóm và công bố số nhóm độc lập, số mẫu và số nhãn thiếu theo lớp/trường. Kiểm giao nhau giữa tập theo nhóm, văn bản gần trùng và nguồn biến thể trước khi khóa manifest.

| Vai trò | Dùng để làm gì |
| --- | --- |
| Train | Fit vectorizer và mô hình |
| Development | So ứng viên và siêu tham số trên validation theo nhóm. Dùng phần dành riêng cho hiệu chuẩn và chọn ngưỡng hoặc dự đoán out-of-fold theo nhóm khi dữ liệu ít |
| Test và challenge | Đánh giá tiếng Việt độc lập. Giữ kín cho tới khi khóa ứng viên, preprocess, bộ hiệu chuẩn, ngưỡng và tiêu chí `AI-07`. Challenge ghi riêng ca biên, ít căn cứ và biến thể ngôn ngữ |

Nếu kết quả test/challenge dẫn đến đổi mô hình hoặc ngưỡng, lượt sau cần tập đánh giá độc lập chưa dùng. Báo Accuracy, Macro-F1, precision/recall/F1 và số mẫu mỗi lớp, confusion matrix, recall `SEC` và coverage–risk theo trường. Giữ mẫu thiếu nhãn trong thống kê, tách khỏi mẫu có nhãn khi tính Accuracy/F1 cho trường đó. [Kế hoạch thực nghiệm](../docs/ml-classifier-plan.md#7-đánh-giá-và-tiêu-chí-chọn)

## Runner tại `main@09ca691`

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
