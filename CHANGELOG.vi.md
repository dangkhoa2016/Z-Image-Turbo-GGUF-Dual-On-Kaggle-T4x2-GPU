# Nhật ký thay đổi

> 🌐 Language / Ngôn ngữ: [English](CHANGELOG.md) | **Tiếng Việt**

## 25/10/2026 — v1.0.0: bản phát hành công khai đầu tiên

- Công bố demo Z-Image-Turbo GGUF Q6_K lấy GitHub làm nguồn, chạy trên Kaggle Tesla T4 ×2, mã hóa prompt có giới hạn trên GPU0 và các worker inference độc lập.
- Phát hành notebook Kaggle song ngữ 28 cell, Vue Studio có xác thực, tài liệu kỹ thuật EN/VI và CPU contract tests.
- Phân phối gallery 170 ảnh watermark có checksum qua GitHub Release, tách biệt khỏi source và model weights.
- Định nghĩa tiêu chí nghiệm thu GPU, Studio, gallery và tái lập độc lập theo Git revision; kết quả kiểm chứng theo Git SHA và artifacts được công bố trên GitHub Release.

## 16/10/2026 — Giai đoạn phát triển (không phải bản phát hành công khai riêng)

- Xây dựng các bản thử nghiệm tạo ảnh dual-T4, Studio xác thực, điều phối job và biên nhận PNG riêng tư.
- Thực hiện các phép thử kỹ thuật ban đầu và chuẩn bị tài liệu về source, API, cài đặt và giấy phép.
- Không đưa receipt runtime lịch sử vào Git tree công khai hiện tại; không dùng chúng làm bằng chứng nghiệm thu mới cho v1.0.0.
