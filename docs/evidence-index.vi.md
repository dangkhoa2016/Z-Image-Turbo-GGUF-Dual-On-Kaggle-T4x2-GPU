# Chỉ mục bằng chứng

> 🌐 Language / Ngôn ngữ: [English](evidence-index.md) | **Tiếng Việt**

## Bằng chứng PASS từ Kaggle runtime trước
- [Dual GPU E2E](../evidence/dual-gpu-inference-acceptance-2026-10-16.json): hai job PNG trên GPU0/GPU1, có bằng chứng GPU sử dụng cùng thời điểm và receipt SHA256.
- [Chromium browser tạo PNG](../evidence/browser-image-generation-acceptance-2026-10-16.json): ảnh 1024×1024, View/Download thành công, không lỗi JS.
- [Tổng thời gian xử lý](../evidence/studio-elapsed-time-acceptance-2026-10-16.json): hiển thị giây cho 6 job completed.
- [HTTPS browser](../evidence/studio-https-browser-acceptance-2026-10-16.json): đăng nhập, xem 3 ảnh cũ và đăng xuất bằng URL tunnel tạm thời.

## Giới hạn đánh giá chất lượng ảnh và kiểm thử môi trường mới
Pilot32 từng có kết quả **NOT_PASS** về chất lượng ảnh và độ đúng prompt; các ca bị loại vẫn được giữ trong bằng chứng. Không có gallery HTML gốc 48/122 trong runtime hiện tại. Repo và notebook sau rewrite CHƯA PASS clean-run Kaggle. JSON phản ánh kiểm thử trước, không khẳng định cloud đang online. Không đóng gói mật khẩu, API key hay PNG riêng tư.
