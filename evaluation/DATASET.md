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
