# Dashboard CDRNN — gói GitHub + Cloudflare Worker/D1

## Chức năng trong gói
- Giao diện chia thành các khu vực: Tổng quan, Sinh viên, Sinh viên cần chăm sóc, Theo trường, Quản trị người dùng.
- ADMIN có quyền quản trị người dùng và nhập/cập nhật dữ liệu sinh viên bằng CSV.
- Tài khoản phụ có vai trò giới hạn (BGH/ĐHĐN, ĐHNN/KT&ĐBCLGD, Trường thành viên, Khoa/CVHT). API kiểm tra quyền phía máy chủ; ẩn tab trên giao diện không phải là biện pháp bảo mật duy nhất.
- Nhập CSV có ghi nhật ký và chỉ tài khoản có quyền `manage_data` mới thực hiện được.
- Cấu hình Worker phục vụ cả giao diện và API cùng một origin; đây là cách phù hợp với các đường dẫn `/api/...` và cookie phiên hiện tại.

## Tệp
- `src/index.js`: Worker API, đăng nhập, phân quyền, quản trị người dùng, nhập dữ liệu.
- `public/index.html`: giao diện Dashboard.
- `migrations/0001_initial.sql`, `migrations/0002_rbac.sql`: cấu trúc D1.
- `wrangler.toml`: binding Assets và D1.

## Cảnh báo quan trọng
1. Đây là gói cập nhật mã nguồn; chưa được kiểm thử trên tài khoản Cloudflare thực tế của bạn. Không ghi đè bản đang chạy trước khi sao lưu.
2. `wrangler.toml` đang chứa database ID `0ed9e5c6-5643-47ed-853b-b6a9f5524792` đã dùng trong dự án. Kiểm tra ID có đúng trong tài khoản Cloudflare của bạn.
3. Cơ sở dữ liệu hiện tại đã có schema và dữ liệu/tài khoản riêng. Đừng chạy migration mù quáng hoặc tạo lại D1. Sao lưu trước, sau đó đối chiếu schema. Migration `CREATE TABLE IF NOT EXISTS` không tự sửa cấu trúc cột đã tồn tại.
4. Gói này **không chứa mật khẩu ADMIN mặc định**. Tiếp tục dùng tài khoản ADMIN đã tạo trong D1 hiện tại; nếu không đăng nhập được thì cần kiểm tra đúng D1 binding và hash mật khẩu, không tự ý xóa bảng tài khoản.
5. Cấu trúc import trong gói cập nhật bản ghi theo `student_code`, phù hợp schema migration của gói. Nếu D1 hiện tại có ràng buộc/schema khác, cần kiểm tra câu SQL trước khi deploy.
6. CSV chứa dữ liệu sinh viên là dữ liệu cần bảo vệ. Không commit dữ liệu thật lên repository GitHub công khai.

## Định dạng CSV
Cột: `student_code,full_name,school_code,major,cohort,class_name`
Mã trường: `SPKT`, `BKA`, `SP`, `DUE`, `VKU`, `YD`.

Ví dụ:
```csv
student_code,full_name,school_code,major,cohort,class_name
SV0001,Nguyen Van A,SPKT,Ngon ngu Anh,K22,22NNA1
```
Tệp CSV phải được rà soát trước khi nhập. Mã sinh viên đã tồn tại sẽ được cập nhật, không tạo bản ghi dự thi riêng cho từng lần thi vì schema hiện tại chỉ lưu hồ sơ sinh viên cơ bản.

## Cách đưa mã nguồn lên GitHub
1. Tải ZIP và giải nén trên máy.
2. Mở repo `phuongktdhnn-afk/CDRNN` trên GitHub.
3. Khuyến nghị tạo branch thử nghiệm trước, ví dụ `test-cdrnn-update`.
4. Tải nội dung bên trong `CDRNN_Dashboard_Ready` lên đúng thư mục gốc repository; không tạo thêm một lớp thư mục lồng nhau.
5. Kiểm tra `wrangler.toml`, đặc biệt `database_id`, trước khi commit.
6. Không triển khai lên production trước khi kiểm tra schema và sao lưu D1.

## Triển khai khuyến nghị
Ứng dụng hiện là **Cloudflare Worker + Static Assets + D1**, không phải một trang Pages tĩnh độc lập. Không triển khai riêng thư mục `public` thành Pages nếu chưa cấu hình Pages Functions/proxy để chuyển tiếp `/api/...` tới API và chia sẻ cùng origin/cookie. Tiếp tục Worker hiện tại là đường triển khai ít rủi ro hơn.

Nếu repo đang nối CI/CD với Worker, commit branch thử nghiệm sẽ có thể kích hoạt deploy tùy cấu hình. Hãy kiểm tra cấu hình deployment trước khi commit vào branch production. Sau deploy, kiểm tra `/api/health`, đăng nhập ADMIN, quyền tài khoản phụ và nhập thử 1–2 dòng dữ liệu giả trước khi nhập dữ liệu thật.
