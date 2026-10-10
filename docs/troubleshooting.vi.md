# Khắc phục lỗi

> 🌐 Language / Ngôn ngữ: [English](troubleshooting.md) | **Tiếng Việt**

## Notebook không khởi động
Kiểm tra T4×2, phiên bản model/dataset đã attach, Internet cho lần tải vendor ban đầu và thư mục làm việc của notebook có thể truy cập. Runtime dở dang không được tự ghi đè.

## Thiếu hai gallery gốc
Khôi phục gói gallery 170 ảnh từ GitHub Release, xác minh SHA256 và manifest, rồi kiểm tra đầy đủ hai trang HTML gallery.

## Worker GPU lỗi
Đối chiếu Python/PyTorch/Transformers/Diffusers/TorchAO và nguồn archive. Chỉ tái sử dụng kết quả PASS cũ khi môi trường tương ứng thực sự được chạy. Không lộ token trong log.

## Lỗi 401 hoặc URL HTTPS mất
Dùng tài khoản demo in trong cell Studio. Quick Tunnel thay URL sau restart. Chỉ expose gateway 18789, không mở API 18788.

## PNG hoặc receipt bị thiếu
Kiểm tra trạng thái job và quyền tenant. Không tự tạo receipt giả hay tự replay job uncertain.
