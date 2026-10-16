# Z-Image-Turbo GGUF Dual trên Kaggle T4 ×2

[![Repository audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml/badge.svg)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml)
[![License MIT](https://img.shields.io/badge/Project%20License-MIT-2ea44f)](LICENSE)
[![Model Apache](https://img.shields.io/badge/Model%20License-Apache--2.0-1565c0)](LICENSE-NOTES.vi.md)
[![Language](https://img.shields.io/badge/Docs-English%20%7C%20Ti%E1%BA%BFng%20Vi%E1%BB%87t-835df1)](README.md)

![Platform](https://img.shields.io/badge/Platform-Kaggle-20BEFF?logo=kaggle&logoColor=white)
![GPU](https://img.shields.io/badge/Accelerator-NVIDIA%20T4%20%C3%97%202-76B900?logo=nvidia&logoColor=white)
![Model](https://img.shields.io/badge/Model-Z--Image--Turbo-3459c7)
![Quantization](https://img.shields.io/badge/GGUF-Q6__K-7350a2)
![Output](https://img.shields.io/badge/PNG-1024%20%C3%97%201024-4f687b)

![API](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Studio](https://img.shields.io/badge/Studio-Vue%203-4FC08D?logo=vuedotjs&logoColor=white)
![Queue](https://img.shields.io/badge/Queue-SQLite-0a5885?logo=sqlite&logoColor=white)
![Tunnel](https://img.shields.io/badge/Tunnel-Cloudflare-ef7f1a?logo=cloudflare&logoColor=white)

[![Prior GPU evidence](https://img.shields.io/badge/Dual--GPU%20Evidence-PASS-22863a)](docs/evidence-index.vi.md)
[![Browser E2E](https://img.shields.io/badge/Browser--to--PNG-PASS-22863a)](docs/evidence-index.vi.md)
[![Kaggle Notebook](https://img.shields.io/badge/Kaggle-Launch%20Notebook-20BEFF)](notebooks/kaggle-dual-gpu-production-demo.ipynb)
[![Gallery Showcase](https://img.shields.io/badge/Gallery-Static%20Showcase-506c91)](docs/deployment-profile.vi.md)

> 🌐 Language / Ngôn ngữ: [English](README.md) | **Tiếng Việt**

## Giới thiệu
Trình diễn Z-Image-Turbo GGUF Q6_K trên **hai GPU Tesla T4**, mã hóa prompt có giới hạn trên GPU0, inference độc lập trên GPU0/GPU1, Vue Studio v3 có xác thực, PNG được kiểm tra toàn vẹn và hai website Cloudflare HTTPS tách biệt.

## Khởi động nhanh
1. [Mở Kaggle notebook](notebooks/kaggle-dual-gpu-production-demo.ipynb).
2. Bật GPU T4×2 và Internet; attach model `dangkhoa2016/unsloth-z-image-turbo-gguf`, biến thể `q6-k`, phiên bản 1.
3. Attach dataset hỗ trợ `dangkhoa2016/z-image-turbo-diffusers-support-components`.
4. Chạy các cell theo thứ tự. Cell Studio in tài khoản demo; thông tin xác thực của dịch vụ backend được bảo vệ và không hiển thị.
5. Mở Studio và tạo ảnh; View/Download PNG, thời gian xử lý tổng và spinner SVG đã từng được nghiệm thu.

## Hai website
- Gallery tĩnh: cần attach riêng **gallery gốc 48 và 122 ảnh** vào `/kaggle/working/gallery-48` và `/kaggle/working/gallery-122`. Chúng **chưa có trong runtime hiện tại**. Không dùng Pilot32 (32 ảnh) để thay thế.
- Studio: Cloudflare HTTPS qua gateway có mật khẩu, **không expose API nội bộ trực tiếp**.

## Bằng chứng và hướng dẫn chạy
Hệ thống đã được kiểm chứng với GPU T4×2 và quy trình tạo PNG từ trình duyệt trong môi trường Kaggle tham chiếu. Các báo cáo kỹ thuật được lưu tại [chỉ mục bằng chứng](docs/evidence-index.vi.md). Notebook hỗ trợ khởi chạy một phiên mới; cần xác minh dependencies và các đầu vào model trên chính runtime đó. Xem [môi trường tương thích](docs/runtime-compatibility.vi.md) và [cấu hình trình diễn](docs/deployment-profile.vi.md).

## Tài liệu
[Kiến trúc](docs/architecture.vi.md) · [Kaggle](docs/kaggle.vi.md) · [API](docs/api.vi.md) · [Benchmark](docs/benchmark.vi.md) · [Môi trường chạy](docs/runtime-compatibility.vi.md) · [Cấu hình trình diễn](docs/deployment-profile.vi.md) · [Tổng quan kỹ thuật](docs/engineering-overview.vi.md) · [Giấy phép](LICENSE-NOTES.vi.md).

## Giấy phép
© 2026 Đăng Khoa <i.am@dangkhoa.dev>. MIT chỉ áp dụng cho mã và tài liệu **do dự án tự viết**; [model Apache-2.0](LICENSE-NOTES.vi.md). Không commit weights, ảnh cá nhân, token, SQLite runtime hoặc gallery. Đây là demo, chưa phải production GO.

## Tài liệu bổ sung
[Chỉ mục bằng chứng](docs/evidence-index.vi.md) · [Khắc phục lỗi](docs/troubleshooting.vi.md) · [Nhật ký](CHANGELOG.vi.md) · [Cam kết dự án](PROJECT-CONTRACT.vi.md) · [Ghi chú phát hành](RELEASE_NOTES_v1.0.0-demo.vi.md).
