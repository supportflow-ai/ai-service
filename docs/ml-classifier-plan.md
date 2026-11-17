# Định hướng và kế hoạch mô hình phân loại phiếu

Trạng thái: định hướng đề xuất, chờ chủ dự án và giảng viên hướng dẫn duyệt các mục đánh dấu **[cần duyệt]**. Cập nhật 2026-11-17, đối chiếu `main` tại `751c8a8` và PR #18 (đưa #13, #14 vào `main`). Kiến trúc hiện hành: [architecture.md](architecture.md). Phía backend: `docs/architecture/ai-integration-plan.md` và ADR-016 trong kho `ai-it-service-desk`.

## 1. Bài toán theo đề xuất của giảng viên

Service desk kỹ thuật tiếng Việt. Luồng:

```
Người dùng tạo phiếu → Backend tiếp nhận → AI phân tích, trả gợi ý
→ Backend tính Priority (PriorityMatrix) và chọn nhóm xử lý (RoutingRule)
→ Agent/Lead/Admin kiểm duyệt, phân công → Xử lý → Đóng phiếu
```

| Chức năng | AI Service làm | Backend làm |
| --- | --- | --- |
| Phân loại phiếu | Gợi ý một trong 11 danh mục (ACC, NET, VPN, MAIL, SW, HW, PRINT, ACCESS, EQUIP, SEC, OTHER) | Lưu gợi ý, hiển thị cho người duyệt |
| Đánh giá mức độ | Gợi ý Impact và Urgency (Low, Medium, High) | Tính Priority P1–P4 theo [ma trận](g1-doi-chieu-enum.md) |
| Hỗ trợ định tuyến | Không làm. Chỉ cung cấp Category | `RoutingRule` ánh xạ `TicketCategory → SupportTeam` (ADR-016); người duyệt chốt và phân công |

Hệ quả cho AI Service: **chỉ cần làm tốt ba trường gợi ý và điểm tin cậy**. Hợp đồng v1 đã đủ cho cả ba trường nên không cần đổi hợp đồng. Lỗi Category nặng nhất là lỗi làm phiếu đi sai nhóm, nên phần đánh giá đo riêng loại lỗi này (mục 5).

Tìm tài liệu liên quan (Knowledge, ý tưởng ban đầu) là P2, ngoài MVP theo tài liệu kiến trúc v3.0 ngày 15/11/2026. Mã `knowledge-indexes:prepare` và embedding E5 giữ nguyên, không phát triển thêm cho đến khi có quyết định mới.

## 2. Ràng buộc đã chốt (chủ dự án, 2026-11-13)

1. MVP tích hợp **mô hình phân loại thật**.
2. Mô hình chạy **cục bộ**, không gọi API hay dịch vụ model bên ngoài. Dữ liệu phiếu không rời hệ thống.
3. AI chỉ gợi ý. Backend giữ quyền ghi, phân quyền, audit; người duyệt quyết định cuối.
4. Điểm số phải được hiệu chỉnh hoặc để `null`. Backend chia dải tin cậy: Thấp dưới 0,4; Cao từ 0,75.

## 3. Hiện trạng (sau PR #18)

| Phần | Trạng thái |
| --- | --- |
| Rule baseline (`rule`) | Category theo từ khóa; không khớp thì `suggestions: []`; `OTHER` chỉ khi có từ khóa máy chủ/hạ tầng. Impact/Urgency chỉ mức `High` theo rubric E0. `score: null` |
| Đánh giá | `evaluation/metrics.py` có Accuracy, Macro-F1, F1 từng lớp, ma trận nhầm lẫn, `coverage`, `selectiveAccuracy` |
| Dữ liệu | Chỉ có 11 mẫu smoke. **Chưa có dữ liệu huấn luyện và gold set**: đây là việc chặn mọi bước sau |
| Hạ tầng ML | Stage `embeddings` của Dockerfile đã có `torch` CPU, `transformers`, `sentence-transformers` (dùng cho E5) |

## 4. Ba phương án so sánh

Theo yêu cầu của giảng viên: so sánh Rule-based, TF-IDF + mô hình tuyến tính, PhoBERT trên **cùng một gold set**, chọn theo chất lượng và hiệu năng thực tế.

| | Rule-based | TF-IDF + tuyến tính | PhoBERT |
| --- | --- | --- | --- |
| Trạng thái | Đã có, làm mốc so sánh | Cần làm | Cần làm |
| Cách làm | Từ khóa, rubric E0 | n-gram ký tự (2–5) và từ (1–2), hồi quy logistic hoặc LinearSVC; mỗi trường một mô hình | Tinh chỉnh `vinai/phobert-base-v2` với đầu phân loại cho từng trường (hoặc một mô hình ba đầu) |
| Tiếng Việt không dấu, viết tắt | Phải liệt kê tay | n-gram ký tự chịu được khá tốt, không cần tách từ | Cần tách từ trước (PhoBERT huấn luyện trên văn bản đã tách từ); văn bản không dấu lệch phân phối pretrain |
| Dữ liệu cần | Không | Vài trăm đến một nghìn mẫu là chạy được | Nhiều hơn để vượt TF-IDF rõ rệt |
| Điểm tin cậy | Không có (`null`) | Hiệu chỉnh bằng `CalibratedClassifierCV` trên tập kiểm định | Hiệu chỉnh bằng temperature scaling trên tập kiểm định |
| Chạy CPU | Tức thời | Vài mili giây, tệp mô hình vài MB | Khoảng 135 triệu tham số, tệp vài trăm MB; độ trễ phải đo |
| Phụ thuộc mới | Không | `scikit-learn` | Bộ tách từ tiếng Việt (VnCoreNLP cần Java, hoặc thư viện Python); **kiểm tra giấy phép trước khi chọn** |

Dự đoán trước (cần số liệu xác nhận): với dữ liệu ít, TF-IDF thường ngang hoặc hơn PhoBERT; PhoBERT có lợi khi phiếu diễn đạt đa dạng, không trùng từ khóa. Vì vậy làm TF-IDF trước, rồi PhoBERT, và **không chọn mô hình trước khi có số liệu**.

Phương án phụ, không bắt buộc: đầu phân loại hồi quy logistic trên embedding E5 đã có trong image. Chi phí thấp, có thể thêm vào bảng so sánh nếu còn thời gian.

Mã huấn luyện đặt ở thư mục `training/` riêng, chạy ngoại tuyến, không nằm trong gói `supportflow_ai`. Mô hình được chọn mới vào `adapters/classifiers/` thành provider `ml`.

## 5. Dữ liệu tiếng Việt: lấy ở đâu

Không có bộ phiếu IT tiếng Việt công khai, có gán nhãn và giấy phép rõ ràng mà dự án dựa vào được. Đề xuất theo thứ tự ưu tiên:

| Nguồn | Vai trò | Ghi chú |
| --- | --- | --- |
| A. Nhóm tự viết theo **thẻ kịch bản** | Nguồn chính cho huấn luyện và gold set | Mỗi thẻ: danh mục, Impact, Urgency, tình huống (ví dụ "cả phòng kế toán mất VPN, sáng nay nộp báo cáo"). Nhiều người viết, bắt buộc đa dạng: có dấu, không dấu, viết tắt ("k vào đc"), xen tiếng Anh, câu cụt, phiếu mơ hồ |
| B. Phiếu từ hệ thống demo và buổi thử người dùng | Bổ sung, sát thực tế hơn | Nhãn = danh mục người duyệt chốt; ẩn danh hóa trước khi dùng |
| C. Nhãn yếu từ phiếu đã đóng | Về lâu dài | Cặp (danh mục người gửi chọn, danh mục nhân viên chốt). Backend cần thêm `RequesterCategoryId`. Không thay gold set |
| D. Phỏng theo bộ dữ liệu ticket công khai tiếng Anh | Chỉ để tham khảo tình huống | Phải kiểm giấy phép. Không dịch bằng API bên ngoài nếu chủ dự án chưa cho phép **[cần duyệt]** |

Quy mô đề xuất **[cần duyệt]**:

- Huấn luyện và kiểm định: khoảng 100–150 mẫu mỗi danh mục (khoảng 1.100–1.650 mẫu), tỷ lệ 80/20.
- Gold set: ít nhất 30 mẫu mỗi danh mục (khoảng 330 mẫu), **do người khác viết và từ thẻ kịch bản khác** so với tập huấn luyện. Không dùng để chọn siêu tham số.
- Chia theo nhóm (người viết, thẻ kịch bản), không chia ngẫu nhiên từng câu, và loại câu gần trùng giữa các tập. Nếu không làm vậy, điểm số sẽ cao giả.

Gán nhãn theo [DATASET.md](../evaluation/DATASET.md): taxonomy có phiên bản, hai người gán độc lập, báo độ đồng thuận (Cohen's kappa), người thứ ba phân xử bất đồng.

Rubric Impact/Urgency cho gán nhãn, bản nháp mở rộng từ E0 **[cần duyệt]**:

| Mức | Impact (phạm vi ảnh hưởng) | Urgency (mức gấp) |
| --- | --- | --- |
| High | Phòng ban, toàn công ty hoặc dịch vụ dùng chung (mail, VPN, server) | Bị chặn làm việc **và** (hạn trong ngày hoặc liên quan an toàn thông tin) |
| Medium | Một nhóm vài người | Bị chặn nhưng chưa có hạn gấp, hoặc vẫn làm việc được với chất lượng giảm |
| Low | Một người | Yêu cầu, hỏi đáp, không chặn công việc |

Dữ liệu tự viết không chứa thông tin cá nhân thật nên được lưu trong Git (`evaluation/data/`, có phiên bản). Dữ liệu từ nguồn B và C phải ẩn danh hóa, không đưa vào Git.

## 6. Đánh giá và tiêu chí chọn

Chạy cả ba phương án qua cùng bộ đánh giá (`evaluation/`), mỗi báo cáo ghi SHA mã, phiên bản dữ liệu và phiên bản mô hình.

| Chỉ số | Áp dụng | Lý do |
| --- | --- | --- |
| Macro-F1, F1 từng lớp, ma trận nhầm lẫn | Category, Impact, Urgency | Chỉ số chính; theo DATASET.md |
| Tỷ lệ lỗi định tuyến | Category | Nhầm giữa hai danh mục thuộc hai `SupportTeam` khác nhau theo `RoutingRule` của Backend. Nhầm trong cùng nhóm ít hại hơn |
| Recall mức High | Impact, Urgency | Bỏ sót phiếu khẩn đắt hơn báo nhầm |
| Khớp Priority | Impact + Urgency | Tính P1–P4 từ gợi ý và từ nhãn qua ma trận; báo tỷ lệ khớp đúng và lệch một mức |
| `coverage`, `selectiveAccuracy` theo ngưỡng | Cả ba trường | Chọn ngưỡng abstain trên tập kiểm định |
| Độ hiệu chỉnh (ECE, biểu đồ tin cậy) | Mô hình có điểm | Để dải 0,4/0,75 của Backend có nghĩa |
| Độ trễ p95 trên CPU, dung lượng mô hình, RAM | Cả ba | "Hiệu năng thực tế" theo yêu cầu |

Tiêu chí chọn, phải chốt **trước** khi chạy trên gold set **[cần duyệt]**:

1. Ưu tiên Macro-F1 Category trên gold set; cùng với đó tỷ lệ lỗi định tuyến không cao hơn mô hình kế tiếp.
2. Nếu hai phương án chênh nhau dưới 0,02 Macro-F1 thì chọn phương án nhẹ hơn.
3. Độ trễ p95 dưới 300 ms trên CPU của máy chạy Compose (Backend chờ tối đa 5 giây mặc định).
4. Mô hình mới chỉ thay `rule` khi vượt `rule` trên gold set. Impact/Urgency có thể giữ rubric E0 nếu mô hình chưa vượt được.

## 7. Đưa mô hình vào dịch vụ

- Provider `ml` trong `adapters/classifiers/`, đăng ký ở `bootstrap.py`, chọn bằng `SUPPORTFLOW_AI_CLASSIFIER_PROVIDER=ml`. `rule` và `noop` giữ làm phương án lùi.
- Artifact có tên, phiên bản, SHA-256; tải lúc build, chạy ngoại tuyến, không `trust_remote_code`. Phụ thuộc ML chỉ ở stage riêng của Dockerfile như stage `embeddings`, không vào `requirements-runtime.lock`.
- Trả điểm đã hiệu chỉnh. Dưới ngưỡng abstain thì bỏ trường đó khỏi `suggestions` thay vì đoán.
- Lỗi tải mô hình thì `/health/ready` trả 503. Không ghi log `title`, `description`.
- Kiểm thử: tính xác định, điểm trong [0, 1], hợp đồng v1 qua HTTP trong container, `test_architecture_boundaries`.

## 8. Lộ trình

| Giai đoạn | Việc | Xong khi |
| --- | --- | --- |
| 0 | Merge PR #18. Duyệt các mục **[cần duyệt]**: nguồn dữ liệu, quy mô, rubric, tiêu chí chọn | Có biên bản duyệt |
| 1 | Viết thẻ kịch bản, hướng dẫn gán nhãn; nhóm viết và gán nhãn; tách gold set | Dữ liệu có phiên bản, báo kappa |
| 2 | Mở rộng `evaluation/` với các chỉ số mục 6 (lỗi định tuyến, khớp Priority, ECE, độ trễ); chạy lại Rule-based làm mốc | Báo cáo mốc có SHA |
| 3 | Huấn luyện TF-IDF + tuyến tính, hiệu chỉnh điểm, báo cáo | Báo cáo có SHA |
| 4 | Tinh chỉnh PhoBERT (sau khi chốt bộ tách từ và giấy phép), hiệu chỉnh, đo độ trễ CPU | Báo cáo có SHA |
| 5 | Bảng so sánh ba phương án, chọn theo tiêu chí đã duyệt | Chủ dự án ký chọn |
| 6 | Provider `ml`, đóng gói, CI, build image | CI và kiểm chứng HTTP trong container đạt |
| 7 | Chạy bóng với Backend (so `ml` với `rule`, chưa hiện cho người dùng), rồi bật theo môi trường | Báo cáo chênh lệch; có đường lùi về `rule` |

Phụ thuộc: Backend lưu và hiển thị gợi ý cho cả ba trường, cung cấp bảng `RoutingRule` để đo lỗi định tuyến, thêm `RequesterCategoryId` cho nguồn C. Infra cấp chỗ lưu artifact mô hình.

## 9. Quyết định còn mở

1. Quy mô dữ liệu, ai viết, ai gán nhãn, ai phân xử (mục 5).
2. Có cho phép dịch hoặc sinh dữ liệu bằng công cụ bên ngoài **khi chuẩn bị dữ liệu** (không phải lúc chạy dịch vụ) hay không.
3. Rubric Impact/Urgency mức Low/Medium (mục 5).
4. Tiêu chí chọn và ngưỡng (mục 6).
5. Bộ tách từ cho PhoBERT và giấy phép của nó; có chấp nhận phụ thuộc Java trong image hay không.
6. Nơi lưu artifact mô hình (trong image hay volume do infra cấp).

## 10. Tài liệu phải cập nhật khi triển khai

[architecture.md](architecture.md), [DATASET.md](../evaluation/DATASET.md), [AGENTS.md](../AGENTS.md), README (bảng trạng thái, chỉ khi mô hình thật đã vào `main`), [cẩm nang chung](team-handbook.md).
