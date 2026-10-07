# Chỉ mục bằng chứng

> 🌐 Language / Ngôn ngữ: [English](evidence-index.md) | **Tiếng Việt**

## Bằng chứng PASS từ Kaggle runtime trước
- [Dual GPU E2E](../evidence/dual-gpu-inference-acceptance-2026-10-16.json): hai job PNG trên GPU0/GPU1, có bằng chứng GPU sử dụng cùng thời điểm và receipt SHA256.
- [Chromium browser tạo PNG](../evidence/browser-image-generation-acceptance-2026-10-16.json): ảnh 1024×1024, View/Download thành công, không lỗi JS.
- [Tổng thời gian xử lý](../evidence/studio-elapsed-time-acceptance-2026-10-16.json): hiển thị giây cho 6 job completed.
- [HTTPS browser](../evidence/studio-https-browser-acceptance-2026-10-16.json): đăng nhập, xem 3 ảnh cũ và đăng xuất bằng URL tunnel tạm thời.

- [Nghiệm thu Kaggle T4x2 và Studio ngày 18/10](../evidence/kaggle-t4x2-studio-acceptance-2026-10-18.json): 2/2 biên nhận GPU portable, 5 job completed và 1 cancelled; người dùng xác nhận View/Download và độ đúng prompt. Thời gian diffusion 9 bước từ log không phải tổng thời gian generation.

## Giới hạn đánh giá chất lượng ảnh và kiểm thử môi trường mới
Archive gallery đã công bố có thể kiểm tra qua manifest; điều này không có nghĩa tất cả ảnh đều đạt tiêu chí chất lượng hoặc bám sát prompt. Tại thời điểm các kiểm thử lưu trữ được thực hiện, hai gallery HTML gốc 48/122 không có trong runtime tham chiếu; bộ gallery song ngữ 170 ảnh đã được công bố sau đó dưới dạng GitHub Release asset. Việc kiểm thử lại notebook đã công bố từ đầu trên một môi trường Kaggle sạch vẫn đang chờ nghiệm thu. JSON phản ánh kiểm thử trước, không khẳng định cloud đang online. Không đóng gói mật khẩu, API key hay PNG riêng tư.
