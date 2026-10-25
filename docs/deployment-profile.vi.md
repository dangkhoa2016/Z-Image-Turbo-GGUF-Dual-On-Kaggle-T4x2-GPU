# Cấu hình triển khai trình diễn

> 🌐 Language / Ngôn ngữ: [English](deployment-profile.md) | **Tiếng Việt**

## Kiến trúc trình diễn

Dự án cung cấp hai website HTTPS tách biệt cho Kaggle T4 ×2:

- **Generation Studio:** giao diện Vue đã nghiệm thu cho luồng nhập prompt → tạo ảnh, trạng thái queued/running/completed, hiệu ứng loading, tổng thời gian xử lý và View/Download PNG. Cloudflare tunnel trỏ tới gateway có mật khẩu ở cổng `18789`, không trỏ trực tiếp tới API nội bộ ở cổng `18788`.
- **Gallery benchmark:** webserver HTML tĩnh riêng để hiển thị **gallery gốc 48 ảnh và 122 ảnh**. HTML và file ảnh tương ứng được cung cấp riêng dưới dạng tài nguyên trình diễn tùy chọn, không kèm trong Git repository. Chỉ dùng archive trong GitHub Release để đại diện cho hai gallery công khai.

## Hồ sơ vận hành

Hai Tesla T4 cho phép worker inference độc lập; giai đoạn mã hóa prompt có giới hạn trên GPU0 và VRAM quyết định throughput. Phiên Kaggle không tồn tại vĩnh viễn và URL Cloudflare Quick Tunnel thay đổi sau khi khởi động lại. Notebook in **mật khẩu demo dùng riêng cho phiên** để người xem đăng nhập, không in service secret nội bộ. Không đưa PNG riêng tư, SQLite runtime hoặc model weights lên Git công khai; cần xuất dữ liệu trước khi tắt máy nếu muốn lưu giữ.

## Bằng chứng và phạm vi

[Chỉ mục kiểm chứng](evidence-index.vi.md) liệt kê bằng chứng cần thu thập trước khi nghiệm thu GPU, browser và tính toàn vẹn ảnh của revision mới. PASS kỹ thuật không đồng nghĩa ảnh đạt mọi tiêu chí QC; việc duyệt trình bày gallery không đồng nghĩa tất cả ảnh đều đạt chất lượng hoặc độ bám sát prompt. Dự án nhằm trình diễn hệ thống tạo ảnh có bằng chứng, không cam kết SLA production hay hosting công khai vĩnh viễn.

[Tương thích môi trường](runtime-compatibility.vi.md) · [Kaggle](kaggle.vi.md) · [Giấy phép](../LICENSE-NOTES.vi.md)
