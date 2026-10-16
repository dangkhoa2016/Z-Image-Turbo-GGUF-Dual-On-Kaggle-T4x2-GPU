# Z-Image-Turbo GGUF Dual trên Kaggle T4 ×2

[![Kiểm tra repo](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml/badge.svg)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml)
![Python](https://img.shields.io/badge/Python-3.13-blue) ![Kaggle](https://img.shields.io/badge/Kaggle-T4%C3%972-20BEFF) [![MIT](https://img.shields.io/badge/Project-MIT-green)](LICENSE) [![Apache](https://img.shields.io/badge/Model-Apache--2.0-orange)](LICENSE-NOTES.vi.md)

> 🌐 Language / Ngôn ngữ: [English](README.md) | **Tiếng Việt**

## Giới thiệu
Trình diễn Z-Image-Turbo GGUF Q6_K trên **hai GPU Tesla T4**, mã hóa prompt có giới hạn trên GPU0, inference độc lập trên GPU0/GPU1, Vue Studio v3 có xác thực, PNG được kiểm tra toàn vẹn và hai website Cloudflare HTTPS tách biệt.

## Khởi động nhanh
1. [Mở Kaggle notebook](notebooks/kaggle-dual-gpu-production-demo.ipynb).
2. Bật GPU T4×2 và Internet; attach model `dangkhoa2016/unsloth-z-image-turbo-gguf`, biến thể `q6-k`, phiên bản 1.
3. Attach dataset hỗ trợ `dangkhoa2016/z-image-turbo-diffusers-support-components`.
4. Chạy các cell theo thứ tự. Cell Studio in tài khoản demo; khóa service nội bộ không được in.
5. Mở Studio và tạo ảnh; View/Download PNG, thời gian xử lý tổng và spinner SVG đã từng được nghiệm thu.

## Hai website
- Gallery tĩnh: cần attach riêng **gallery gốc 48 và 122 ảnh** vào `/kaggle/working/gallery-48` và `/kaggle/working/gallery-122`. Chúng **chưa có trong runtime hiện tại**. Không dùng Pilot32 (32 ảnh) để thay thế.
- Studio: Cloudflare HTTPS qua gateway có mật khẩu, **không expose API nội bộ trực tiếp**.

## Khả năng tái lập
Runtime Kaggle trước đã chứng minh inference song song và tạo PNG từ browser. **Repo rewrite và notebook này chưa được chạy sạch đầu-cuối**. Không đưa vào cây nguồn các thư viện vendor quá lớn; xem [tái lập](docs/reproducibility.vi.md).

## Tài liệu
[Kiến trúc](docs/architecture.vi.md) · [Kaggle](docs/kaggle.vi.md) · [API](docs/api.vi.md) · [Benchmark](docs/benchmark.vi.md) · [Tái lập](docs/reproducibility.vi.md) · [Giới hạn](docs/limitations.vi.md) · [Lịch sử](docs/development-history.vi.md) · [Giấy phép](LICENSE-NOTES.vi.md).

## Giấy phép
© 2026 Đăng Khoa <i.am@dangkhoa.dev>. MIT chỉ áp dụng cho mã và tài liệu **do dự án tự viết**; [model Apache-2.0](LICENSE-NOTES.vi.md). Không commit weights, ảnh cá nhân, token, SQLite runtime hoặc gallery. Đây là demo, chưa phải production GO.
