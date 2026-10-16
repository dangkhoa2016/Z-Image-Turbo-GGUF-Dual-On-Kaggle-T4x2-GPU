# v1.0.0-demo — Bản xem trước kỹ thuật

> 🌐 Language / Ngôn ngữ: [English](RELEASE_NOTES_v1.0.0-demo.md) | **Tiếng Việt**

Bản xem trước công khai đầu tiên giới thiệu source hệ thống Z-Image-Turbo GGUF Q6_K trên Kaggle hai Tesla T4: bộ mã hóa prompt có giới hạn, worker inference độc lập, Vue Studio xác thực, biên nhận PNG và notebook khởi chạy.

### Nghiệm thu và giới hạn
- Đính kèm bằng chứng JSON từ các lần thử dual-GPU, browser click-to-image, thời gian hiển thị và HTTPS.
- Kiểm thử CI của GitHub không thay thế nghiệm thu GPU trên môi trường sạch.
- Pilot32 visual quality / prompt adherence trước đây: **NOT_PASS**.
- Chạy lại Kaggle T4×2 từ môi trường sạch: **PENDING**.
- Không phân phối HTML gallery gốc 48/122 ảnh hay model weights của bên thứ ba.
- Tunnel tạm thời và bản prerelease không cam kết SLA production.

Xem [tổng quan kỹ thuật](docs/engineering-overview.vi.md), [hướng dẫn tương thích](docs/runtime-compatibility.vi.md) và [giấy phép](LICENSE-NOTES.vi.md) để nắm phạm vi nghiệm thu và yêu cầu môi trường.
