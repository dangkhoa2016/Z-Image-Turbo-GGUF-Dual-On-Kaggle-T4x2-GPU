# v1.0.0-demo — Bản xem trước kỹ thuật

> 🌐 Language / Ngôn ngữ: [English](RELEASE_NOTES_v1.0.0-demo.md) | **Tiếng Việt**

Bản xem trước kỹ thuật công bố mã nguồn hệ thống Z-Image-Turbo GGUF Q6_K trên Kaggle hai Tesla T4: mã hóa prompt trên GPU0, hai worker inference, Vue Studio xác thực, biên nhận PNG riêng tư, notebook Kaggle và tài liệu song ngữ.

## Nghiệm thu
- Đính kèm bằng chứng JSON về dual-GPU, tạo ảnh qua trình duyệt, tổng thời gian xử lý và HTTPS.
- CI GitHub kiểm tra cấu trúc mã nguồn/tài liệu, không thay thế kiểm thử GPU trong runtime mới.
- Bài đánh giá Pilot32 về độ bám prompt và chất lượng ảnh trước đây: **NOT_PASS**.
- Cài đặt sạch trên Kaggle T4×2 và chạy lại đầu-cuối: **PENDING**.

## Phân phối và hỗ trợ
- Không đóng gói model weights bên thứ ba; attach model và dataset hỗ trợ trên Kaggle.
- Chưa kèm các HTML gallery gốc 48/122 ảnh.
- HTTPS tunnel hoạt động tạm thời, bản demo không cam kết SLA vận hành production.

Xem [tổng quan kỹ thuật](docs/engineering-overview.vi.md), [môi trường tương thích](docs/runtime-compatibility.vi.md), [chỉ mục bằng chứng](docs/evidence-index.vi.md) và [giấy phép](LICENSE-NOTES.vi.md).
