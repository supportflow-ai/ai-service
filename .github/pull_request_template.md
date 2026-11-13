## 1. Nội dung và lý do thay đổi

<!-- Nêu vấn đề, hành vi sau thay đổi và phạm vi chịu ảnh hưởng (route, provider, hợp đồng, Dockerfile). -->

- Loại thay đổi: [ ] Tính năng  [ ] Sửa lỗi  [ ] Tái cấu trúc  [ ] Bảo trì  [ ] Tài liệu
- Mã công việc hoặc liên kết (nếu có, không bắt buộc):

## 2. Bằng chứng kiểm thử

<!-- Ghi lệnh thực sự đã chạy, kết quả và SHA được kiểm chứng. Không chỉ đánh dấu ô. -->

```sh
ruff check .
pytest
python scripts/validate_ai_contract.py
python -m evaluation.run_classification
python -m compileall -q src evaluation scripts
```

- SHA đã kiểm chứng:
- Kết quả, số kiểm thử đạt/thất bại/bỏ qua:
- Build image và xác minh HTTP trong container (nếu đổi Dockerfile, dependency, cấu hình):
- Kiểm tra không chạy và lý do, nếu có:

## 3. Ảnh hưởng tới kho khác

Đối chiếu [cẩm nang chung](../docs/team-handbook.md#4-thay-đổi-ảnh-hưởng-kho-khác).

- [ ] Không ảnh hưởng kho khác
- [ ] Hợp đồng phân loại v1 hoặc chỉ mục tri thức: đã cập nhật cùng đợt với backend (`contract.lock.json`, SHA nguồn, hash) hoặc ghi rõ việc đồng bộ chưa làm
- [ ] Cổng, health, biến `SUPPORTFLOW_AI_*`, Dockerfile: đã báo kho infra và backend

## 4. Điều kiện hoàn thành

- [ ] CI đạt trên commit mới nhất của PR
- [ ] Có ít nhất một người khác đánh giá; không tự phê duyệt PR của mình
- [ ] Tài liệu liên quan đã cập nhật bằng tiếng Việt, hoặc nêu lý do không cần: 
- [ ] Không có token, khóa hay dữ liệu thật trong mã, log, fixture; không log `title`, `description`, `content`, vector
- [ ] Không sửa test, fixture, `contract.lock.json` hay hợp đồng để làm CI xanh
- [ ] Không phát hành image hay đổi provider mặc định khi chưa được duyệt
