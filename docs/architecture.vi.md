# Kiến trúc hệ thống

> 🌐 Language / Ngôn ngữ: [English](architecture.md) | **Tiếng Việt**

Trình duyệt gửi job qua Vue Studio gateway cổng localhost 18789 đến FastAPI nội bộ 18788. SQLite lưu trạng thái hàng đợi. GPU0 mã hóa prompt; các worker inference độc lập xử lý trên GPU0 và GPU1. Ảnh lưu trong private store và xác minh SHA256, tải qua API xác thực. Encode không nhất thiết song song dù inference chạy hai GPU. Cloudflare tunnel của Studio và gallery phải sử dụng hai webserver tách biệt. Demo đã PASS ở phiên Kaggle trước; chạy lại từ runtime sạch vẫn đang chờ.
