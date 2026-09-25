# Bản sửa hoàn chỉnh – Dashboard CĐR UFLS

## Mục tiêu
Bản này sửa lỗi đăng nhập "Tài khoản hoặc mật khẩu không đúng" bằng cách:
- Có `password_hash` trong D1.
- Hash mật khẩu bằng PBKDF2-SHA256 trên Cloudflare Workers Web Crypto.
- Có session HttpOnly/Secure trong D1.
- Có `/api/health`, `/api/login`, `/api/logout`, `/api/me`, `/api/dashboard`, `/api/students`, `/api/care-cases`.
- Có migration D1.
- Giao diện đăng nhập + dashboard chạy chung trên một Worker, tránh lỗi CORS do tách frontend/backend.

Cloudflare hỗ trợ D1 qua Worker binding và PBKDF2 qua Web Crypto. Xem tài liệu chính thức:
https://developers.cloudflare.com/d1/worker-api/
https://developers.cloudflare.com/workers/runtime-apis/web-crypto/
https://developers.cloudflare.com/d1/reference/migrations/

## 1. Quan trọng trước khi deploy

Mở `wrangler.toml` và thay:

`REPLACE_WITH_YOUR_EXISTING_D1_DATABASE_ID`

bằng **Database ID của D1 hiện tại `cdr-ta-ufl`**.

Không tạo D1 mới nếu muốn giữ dữ liệu hiện tại.

## 2. Nếu deploy bằng GitHub + Cloudflare Workers

Repository cần giữ nguyên cấu trúc:

- `src/index.js`
- `public/index.html`
- `migrations/0001_auth_and_core.sql`
- `wrangler.toml`

Sau khi kết nối GitHub với Worker, deploy theo cấu hình Wrangler.

Nếu Worker đã có binding D1 trên Cloudflare Dashboard, kiểm tra binding phải có:
- Variable name: `DB`
- Database: `cdr-ta-ufl`

Nếu Cloudflare dashboard đang dùng một tên binding khác, sửa `binding = "DB"` cho đúng tên binding hiện tại.

## 3. Chạy migration trên D1 hiện tại

Nếu dùng Wrangler:

`npx wrangler d1 migrations apply DB --remote`

Migration chỉ bổ sung các bảng/column cần thiết bằng `CREATE TABLE IF NOT EXISTS`; không xóa dữ liệu hiện hữu.

## 4. Tạo tài khoản quản trị

Không đặt mật khẩu mặc định trong mã nguồn.

Trên Cloudflare Worker, tạo một Secret tên:

`SETUP_KEY`

Giá trị là một chuỗi bí mật do bạn tự đặt.

Sau khi deploy, gọi POST:

`/api/setup`

Header:

`x-setup-key: <SETUP_KEY>`

Body ví dụ:

{
  "username": "admin.cdr",
  "password": "MAT_KHAU_MOI_TOI_THIEU_10_KY_TU",
  "full_name": "Quản trị Dashboard CĐR",
  "email": "",
  "role_code": "ADMIN"
}

Có thể thực hiện bằng REST client hoặc Cloudflare dashboard.

Sau khi tạo tài khoản, `/api/setup` vẫn yêu cầu `SETUP_KEY`.

## 5. Kiểm tra nhanh

Mở:

`/api/health`

Kết quả mong đợi dạng:

{
  "ok": true,
  "db": true,
  "counts": {
    "users": 1,
    "students": 0,
    "care_cases": 0
  }
}

Nếu `students = 0` thì đó là do D1 hiện chưa có dữ liệu sinh viên; không phải lỗi đăng nhập.

## 6. Tài khoản BGH / DHNN123

Không dùng chung mật khẩu ADMIN.

Tạo một tài khoản riêng:

{
  "username": "dhhn123",
  "full_name": "BGH",
  "role_code": "BGH"
}

Có thể dùng `DHNN123` nếu đó là quy ước tài khoản của hệ thống hiện tại; username được lưu theo đúng chuỗi bạn nhập.

## 7. Lưu ý về dữ liệu hiện tại

Bản `dashboard.html` cũ trong Library là dashboard chạy trực tiếp trên Excel và không có backend authentication/session. File đó đọc Excel bằng thư viện XLSX phía trình duyệt. Bản sửa này chuyển phần xác thực sang Worker + D1, nên không còn phụ thuộc vào việc JavaScript phía trình duyệt tự kiểm tra mật khẩu.

Nếu D1 hiện tại đã có bảng `users` với dữ liệu cũ, migration không tự xóa. Nếu bảng `users` thiếu `password_hash`, cần đảm bảo migration đã bổ sung column này trước khi tạo tài khoản.

## 8. Sau khi đăng nhập

Dashboard hiển thị:
- Tổng sinh viên
- Đã đạt CĐR
- Chưa đạt
- Thống kê theo trường
- Mức cảnh báo
- Danh sách sinh viên
- Danh sách cần theo dõi

Các API đều yêu cầu session, trừ `/api/health`, `/api/login` và `/api/setup`.

## 9. Bảo mật

- Mật khẩu không lưu dạng rõ.
- Session token không lưu trực tiếp trong D1; D1 lưu SHA-256 của token.
- Cookie session là HttpOnly + Secure + SameSite=Lax.
- Không đưa `SETUP_KEY` hoặc mật khẩu vào GitHub.
