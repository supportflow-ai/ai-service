"""Khung cho provider phân loại học máy cục bộ (docs/ml-classifier-plan.md mục 4, PR D5).

- `text`: chuẩn hóa và cắt văn bản, dùng chung cho huấn luyện (`training/`) và suy luận.
- `artifact`: đọc manifest, kiểm SHA-256 từng file trước khi nạp mô hình.
- `inference`: chạy suy luận CPU ngoài event loop, giới hạn song song và hàng chờ.

Chưa đăng ký provider `ml` trong `config.py`/`bootstrap.py`: việc đó làm cùng adapter của mô hình
được chọn (mốc M3), khi đã có artifact thật. Gói này không import thư viện ML nặng.
"""
