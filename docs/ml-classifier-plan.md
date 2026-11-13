# Kế hoạch mô hình phân loại học máy cục bộ

Trạng thái: kế hoạch đề xuất chờ chủ dự án duyệt, chưa triển khai. Cập nhật 2026-11-13, đối chiếu `main` tại `9ebba7f`. Kiến trúc hiện hành: [architecture.md](architecture.md). Phía backend: `docs/architecture/ai-integration-plan.md` trong kho `ai-it-service-desk`.

## 1. Quyết định đã chốt (chủ dự án, 2026-11-13)

1. MVP tích hợp **mô hình phân loại thật**.
2. ai-service dùng **mô hình học máy cục bộ cho cả embedding và phân loại, không gọi API hay dịch vụ model bên ngoài** (không có "tạm thời" hay ngoại lệ theo nhà cung cấp). Dữ liệu phiếu không rời hệ thống.
3. README của ai-service giữ nguyên; bảng trạng thái ở đó chỉ được sửa khi mô hình thật đã vào `main`.
4. Backend tiêu thụ `POST /v1/knowledge-indexes:prepare`.

## 2. Hiện trạng (đã kiểm tra trong mã)

| Phần | Trạng thái |
| --- | --- |
| Phân loại | Provider `rule` (từ khóa, `score = null`, không giả lập xác suất) và `noop` (503 có kiểm soát), chọn bằng `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER` ở `bootstrap.py`; cổng `TicketClassifier.classify(title, description) → ClassificationPrediction` |
| Phân loại: đầu ra theo hợp đồng v1 | Ba trường gợi ý: `category` (11 giá trị: ACC, NET, VPN, MAIL, SW, HW, PRINT, ACCESS, EQUIP, SEC, OTHER), `impact` và `urgency` (Low, Medium, High) |
| Embedding | `local-e5` thật (`intfloat/multilingual-e5-small`, 384 chiều, CPU, tải lúc build, chạy offline) và `noop` |
| Đánh giá | `evaluation/run_classification.py` và `classification_report` trong `evaluation/metrics.py`; `sample-classification.jsonl` chỉ là dữ liệu smoke, **không phải gold set** |
| Gold set | Chưa có. Yêu cầu theo [DATASET.md](../evaluation/DATASET.md): taxonomy có phiên bản, quy tắc gán nhãn, ít nhất hai người duyệt, xử lý bất đồng, không dùng để tinh chỉnh mô hình; báo cáo gồm Accuracy, Macro-F1, F1 từng lớp, ma trận nhầm lẫn |

Backend dùng điểm số để chia dải tin cậy (Thấp dưới 0,4; Cao từ 0,75 trở lên). Điểm của mô hình mới phải **được hiệu chỉnh** để các ngưỡng đó có nghĩa; điểm chưa hiệu chỉnh không được trả về như xác suất.

## 3. Mục tiêu

Provider mới `ml` (tên đề xuất) cho cả ba trường gợi ý, chạy trên CPU, ngoại tuyến, có phiên bản và nguồn gốc mô hình rõ ràng, thay thế `rule` làm mặc định **chỉ khi** đạt tiêu chí đánh giá do chủ dự án duyệt. `rule` và `noop` giữ làm phương án lùi.

## 4. Hướng kỹ thuật (đề xuất, cần chốt sau đánh giá)

Không chọn trước bằng suy đoán. So sánh trên cùng gold set:

| Phương án | Ý tưởng | Ưu | Nhược |
| --- | --- | --- | --- |
| A. Đầu phân loại trên embedding E5 sẵn có | Dùng vector 384 chiều đã có, huấn luyện đầu phân loại nhẹ (ví dụ hồi quy logistic) ngoại tuyến | Tái dùng model và hạ tầng đã có, tệp mô hình nhỏ, suy luận nhanh | Chất lượng phụ thuộc embedding, cần đủ dữ liệu cho từng lớp |
| B. TF-IDF và mô hình tuyến tính | Cổ điển, dựa từ khóa và n-gram | Rất nhẹ, dễ giải thích, cần ít tài nguyên | Yếu với diễn đạt khác từ khóa, cần xử lý tiếng Việt |
| C. Tinh chỉnh transformer | Tinh chỉnh một model nhỏ trên dữ liệu phiếu | Có thể chính xác nhất | Cần nhiều dữ liệu và tài nguyên huấn luyện, artifact lớn, suy luận chậm hơn |

Đề xuất bắt đầu bằng A và B làm cơ sở so sánh (chi phí thấp, chạy cục bộ), chỉ xét C nếu hai phương án đầu không đạt tiêu chí. Impact và Urgency có thể cần nhãn riêng; nếu chưa có nhãn đủ chất lượng thì giữ cách tính hiện có cho hai trường này và chỉ thay Category trước, ghi rõ trong tiêu chí đạt.

## 5. Dữ liệu và gold set

- Nguồn dữ liệu: phiếu lịch sử (chứa thông tin cá nhân) hay dữ liệu tổng hợp; **chưa chốt**. Dữ liệu có thông tin cá nhân phải ẩn danh hóa trước khi dùng, không đưa vào Git, và lưu nơi có kiểm soát truy cập.
- Gold set tách khỏi tập huấn luyện và tập kiểm định, không dùng để tinh chỉnh; có phiên bản taxonomy, quy tắc gán nhãn, hai người duyệt và xử lý bất đồng.
- Mọi lần đánh giá ghi: SHA mã, phiên bản dữ liệu, phiên bản mô hình, số mẫu từng lớp.

## 6. Đóng gói và vận hành

- Artifact mô hình có tên, phiên bản và SHA-256, ghim như profile embedding hiện nay; **tải lúc build, không tải lúc chạy**, không dùng `trust_remote_code`.
- Image: giữ ranh giới hiện nay (phụ thuộc ML nặng chỉ ở stage `embeddings` hoặc một stage tương tự cho mô hình phân loại); không đưa vào `requirements-runtime.lock` mặc định.
- Cấu hình: `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER=ml` (và thư mục mô hình do cấu hình, tên biến chốt khi viết mã); lỗi tải mô hình thì `/health/ready` trả 503, không giả lập dự đoán.
- Hiệu năng: backend hiện đặt thời gian chờ mặc định 5 giây (cấu hình 1 đến 30). Đặt mục tiêu độ trễ suy luận trên CPU cùng tiêu chí đạt; chưa có số đo nên chưa ghi con số.
- Nhật ký: không ghi `title`, `description` hay vector; phiên bản mô hình có thể ghi ở `/health/ready` hoặc nhật ký khởi động (không đổi hợp đồng v1 khi chưa có thỏa thuận với backend).

## 7. Kiểm thử và tiêu chí đạt

- Đơn vị: tính xác định (cùng đầu vào cùng đầu ra, sai số số thực có kiểm soát), từ chối đầu vào ngoài miền, điểm trong khoảng hợp lệ.
- Hợp đồng và tích hợp: giữ nguyên kiểm thử hợp đồng v1; thêm ca cho provider `ml` qua HTTP trong container (tương tự bước xác minh HTTP hiện có).
- Đánh giá: báo cáo Accuracy, Macro-F1, F1 từng lớp, ma trận nhầm lẫn và **độ hiệu chỉnh** của điểm trên gold set; ngưỡng đạt do chủ dự án duyệt trước khi chạy (không chọn ngưỡng sau khi thấy kết quả).
- Kiểm thử kiến trúc: route không gọi thư viện mô hình trực tiếp (`test_architecture_boundaries`).

## 8. Lộ trình

| Giai đoạn | Nội dung | Điều kiện xong |
| --- | --- | --- |
| 0 | Chốt nguồn dữ liệu, taxonomy, tiêu chí đạt và ngưỡng, người duyệt gold set | Chủ dự án duyệt |
| 1 | Xây gold set và tập huấn luyện/kiểm định theo DATASET.md | Gold set có phiên bản |
| 2 | So sánh phương án A và B bằng bộ đánh giá hiện có | Báo cáo đánh giá có SHA |
| 3 | Adapter `ml`, đóng gói artifact, health, kiểm thử | CI và build image đạt |
| 4 | Chạy bóng cùng backend (so sánh `ml` với `rule`, chưa hiển thị cho người dùng) | Báo cáo chênh lệch |
| 5 | Bật `ml` theo môi trường qua cấu hình | Tiêu chí đạt đã duyệt; có phương án lùi về `rule` |

Phụ thuộc: backend (`ai-integration-plan.md` bước 5 đến 7) để lưu và duyệt gợi ý; infra để có chỗ lưu artifact và cache mô hình trong image.

## 9. Tài liệu phải cập nhật khi triển khai

[architecture.md](architecture.md) (mục Provider evolution đã bỏ bước "external LLM adapter" theo quyết định này), [DATASET.md](../evaluation/DATASET.md), [AGENTS.md](../AGENTS.md), README (bảng trạng thái, chỉ sau khi mô hình thật vào `main`), [cẩm nang chung](team-handbook.md) (bốn kho cùng lúc).

## 10. Quyết định còn mở

1. Nguồn dữ liệu huấn luyện và cách ẩn danh hóa.
2. Tiêu chí đạt và ngưỡng (Accuracy, Macro-F1, độ hiệu chỉnh, độ trễ).
3. Có thay Impact và Urgency bằng mô hình ngay hay chỉ Category.
4. Ai duyệt gold set và ai ký tiêu chí đạt.
5. Nơi lưu artifact mô hình (trong image hay volume do hạ tầng cấp) và quy trình cập nhật.
