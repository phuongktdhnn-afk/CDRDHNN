# Triển khai Dashboard lên Internet

Bản này đã sẵn sàng chạy production bằng Gunicorn và nhận cổng từ biến `$PORT`. Ứng dụng lắng nghe `0.0.0.0`, có endpoint kiểm tra `/health`, cookie phiên bảo mật khi bật HTTPS, và hỗ trợ `DB_PATH`/`UPLOAD_DIR` để dùng persistent storage.

## Khuyến nghị: hosting có persistent disk
Vì dữ liệu hiện được lưu bằng SQLite, **bắt buộc dùng persistent disk/volume** nếu muốn dữ liệu thực không mất sau redeploy/restart. File `render.yaml` đã có cấu hình mẫu cho Render với volume `/var/data`. Khi triển khai lần đầu, bạn cần đưa file `cdr_dashboard.db` hiện tại vào volume nếu muốn giữ nguyên dữ liệu đang có.

### Thiết lập chung
- Build: `pip install -r requirements.txt`
- Start: `gunicorn --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT app:app`
- `SECRET_KEY`: tạo một chuỗi ngẫu nhiên riêng cho production; không chia sẻ công khai.
- HTTPS: đặt `SESSION_COOKIE_SECURE=1`.
- SQLite: đặt `DB_PATH` trỏ vào persistent volume.
- Upload Excel: đặt `UPLOAD_DIR` vào persistent volume.

## Render
Có thể dùng trực tiếp `render.yaml` làm Blueprint. Dịch vụ web có persistent disk nên cần gói hỗ trợ disk của nhà cung cấp. Sau khi deploy, Render sẽ cấp một URL HTTPS; URL đó có thể mở trên máy tính, điện thoại và máy tính bảng có Internet.

**Quan trọng:** file database đang nằm trong gói ZIP không tự động được chép vào persistent disk nếu hosting mount volume lên một thư mục khác. Nếu cần giữ dữ liệu hiện tại, hãy sao chép `cdr_dashboard.db` vào đúng vị trí volume trước khi đưa hệ thống vào sử dụng.

## Tài khoản BGH
- Username: `ĐHNN123`
- Mật khẩu ban đầu: `CDRDHNN123`
- Quyền: `viewer`, chỉ xem dashboard tổng hợp.
- Bắt buộc đổi mật khẩu ở lần đăng nhập đầu tiên.

## Tài khoản quản trị
- Username: `admin`
- Mật khẩu ban đầu theo `PASS_DEFAULT` trong `app.py`.
- Đổi mật khẩu ngay sau khi đăng nhập.

## Bảo mật
Không đưa `.secret_key` hoặc `.env` lên Git. Sao lưu SQLite định kỳ. Với quy mô lớn/nhiều người dùng đồng thời, nên chuyển từ SQLite sang PostgreSQL.
