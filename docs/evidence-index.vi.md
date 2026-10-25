# Kiểm chứng GPU và trình duyệt theo từng Git revision

> 🌐 Language / Ngôn ngữ: [English](evidence-index.md) | **Tiếng Việt**

## Xem kết quả nghiệm thu hiện hành ở đâu?

[GitHub Release v1.0.0](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) cung cấp kết quả kiểm chứng GPU, trình duyệt và các artifacts liên quan. Hướng dẫn này xác định bằng chứng cần có để đánh giá mỗi lần thực thi trên Kaggle Tesla T4 ×2. Chỉ công nhận kết quả khi xác minh được Git SHA, phiên bản inputs, outputs và các phép kiểm; **thiếu bằng chứng không đồng nghĩa PASS**.

Notebook phát hành tải source từ GitHub và ghi Git SHA đầy đủ 40 ký tự. Kết quả chỉ áp dụng cho **đúng SHA đó và phiên bản Kaggle inputs được ghi trong báo cáo**. Để tái lập một kết quả cụ thể, đặt `ZIMAGE_SOURCE_SHA` bằng SHA trong bằng chứng trên Release trước khi chạy; nếu không, notebook sẽ tự lấy SHA mới nhất của `main`. Người đánh giá cần đối chiếu Git SHA thực thi với bằng chứng đã công bố.

| Hạng mục | Bằng chứng cần đối chiếu | Điều kiện nghiệm thu |
|---|---|---|
| Source và inputs | Git SHA 40 ký tự, GPU T4 ×2, hai Kaggle model inputs và phiên bản | SHA và inputs khớp báo cáo |
| Ảnh GPU mới | Hai PNG 1024 × 1024 sinh mới, mỗi worker một ảnh, có GPU ID, prompt và seed | Sinh thật trong phiên hiện tại, không tái sử dụng cache |
| Toàn vẹn ảnh và ZIP | SHA256 PNG, `report.json`, `inference-manifest.json` và ZIP | Tính lại từ bytes thực |
| Studio | Gửi prompt qua giao diện xác thực, job completed/archived, View/Download PNG | Browser và receipt đều xác thực |
| Gallery công khai | SHA256 asset, ảnh, hai trang gallery và điều hướng chéo | Kiểm độc lập toàn vẹn và browser |
| Tái lập độc lập | Tài khoản Kaggle khác import notebook Release với đủ inputs | Chỉ PASS nếu đã chạy kiểm thực tế |

## Chạy lại và công bố evidence mới

Tải [notebook Release v1.0.0](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb). Sử dụng phiên Kaggle Tesla T4 ×2 sạch, bật Internet và attach hai model inputs đã hướng dẫn. Đối chiếu Git SHA notebook in ra; giữ PNG từng GPU, seed, worker ID, log, thời gian mỗi worker và tổng thời gian, `report.json`, `inference-manifest.json`, `p23-runall-acceptance.zip`.

Trước khi công bố, xác minh source SHA, bytes PNG, SHA256 và receipt trong ZIP. Loại mật khẩu Studio, token/API secret, media riêng tư và địa chỉ tunnel còn hoạt động. Đính kèm bộ evidence đạt yêu cầu vào GitHub Release, ghi rõ ngày chạy, SHA, GPU, phiên bản model inputs, phạm vi và trạng thái thực tế. Công bố kết quả đã kiểm chứng cùng Git SHA và artifacts trên GitHub Release để cộng đồng có thể tái lập, đối chiếu.

CPU/CI PASS **không** chứng minh GPU đã sinh ảnh, HTTPS hay Studio đã chạy. `PENDING_BROWSER_VERIFICATION` nghĩa là browser chưa được xác nhận và phải kiểm thực tế. Gallery 170 PNG có watermark cùng 40 WebP là bộ ảnh công khai, không phải bằng chứng fresh GPU Run All hay chứng nhận tất cả prompt đạt chất lượng.
