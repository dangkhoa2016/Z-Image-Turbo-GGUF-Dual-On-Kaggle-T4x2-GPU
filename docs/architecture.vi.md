# Kiến trúc hệ thống

> 🌐 Language / Ngôn ngữ: [English](architecture.md) | **Tiếng Việt**

Trình duyệt gửi job qua Vue Studio gateway cổng localhost 18789 đến FastAPI nội bộ 18788. SQLite lưu trạng thái hàng đợi. GPU0 mã hóa prompt; các worker inference độc lập xử lý trên GPU0 và GPU1. Ảnh lưu trong private store và xác minh SHA256, tải qua API xác thực. Encode không nhất thiết song song dù inference chạy hai GPU. Cloudflare tunnel của Studio và gallery phải sử dụng hai webserver tách biệt. Nghiệm thu GPU và tái lập trên tài khoản Kaggle khác cần evidence khớp Git SHA; kết quả hiện hành được công bố trên [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0), không ghi trạng thái động trong source.
