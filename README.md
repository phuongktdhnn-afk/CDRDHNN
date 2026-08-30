# Dashboard theo dõi thi CĐR SV TTV ĐHĐN — Web có phân quyền

## Chức năng
- Đăng nhập thật bằng tài khoản + mật khẩu, mật khẩu lưu dạng hash.
- Quản trị: xem toàn hệ thống, cập nhật Excel, quản lý tài khoản, xuất CSV.
- Tài khoản trường: chỉ truy vấn được dữ liệu của trường được gán; không có quyền cập nhật Excel hoặc xem trường khác.
- Dashboard: KPI, lượt thi theo năm/trường/khóa/đợt, cơ cấu kết quả, so sánh tỷ lệ đạt.
- Cảnh báo: gom lịch sử theo Mã SV; ưu tiên nhóm thi nhiều lần chưa đạt.
- Người dùng bắt buộc đổi mật khẩu lần đầu.

## Chạy nội bộ
1. Cài Python 3.10+.
2. Mở Terminal tại thư mục này.
3. `pip install -r requirements.txt`
4. `python app.py`
5. Mở `http://127.0.0.1:5000`

## Tài khoản khởi tạo
- `admin` — quản trị toàn hệ thống
- Các tài khoản trường có dạng `school_<ten_truong>`.
- Mật khẩu ban đầu: `CDRDHNN123`.
- **Đổi ngay mật khẩu trước khi chia sẻ cho người dùng.**

## Triển khai trong mạng cơ quan
Chạy Flask trên một máy chủ nội bộ và bind host `0.0.0.0` (sửa dòng cuối app.py hoặc đặt sau một reverse proxy). Người dùng truy cập bằng IP/tên máy chủ nội bộ. Không mở cổng ra Internet nếu chưa cấu hình HTTPS, firewall và quản trị mật khẩu.

## Cập nhật Excel
Tài khoản admin → Quản trị dữ liệu → chọn Excel → Cập nhật. File Excel cần giữ cấu trúc header như file nguồn hiện tại, với dòng tiêu đề bảng ở dòng 3.

## Lưu ý bảo mật
Phân quyền được thực hiện ở phía máy chủ bằng SQL WHERE theo trường, không phải chỉ bằng bộ lọc giao diện. Tuy vậy, đây là bản nền tảng; trước khi đưa lên Internet cần HTTPS, SECRET_KEY riêng, mật khẩu mạnh, sao lưu DB và có thể chuyển SQLite sang PostgreSQL nếu số người dùng tăng.


PHÂN QUYỀN BGH TRƯỜNG ĐHNN
----------------------------
- Tài khoản: ĐHNN123
- Mật khẩu ban đầu: CDRDHNN123
- Vai trò: viewer (chỉ xem tổng hợp toàn hệ thống).
- Không được cập nhật Excel, không quản trị tài khoản, không xem trang danh sách/hồ sơ sinh viên, không xuất CSV.
- Bắt buộc đổi mật khẩu lần đầu.
- Có thể tạo thêm tài khoản viewer riêng cho từng thành viên BGH từ trang Quản trị dữ liệu bằng tài khoản admin.
