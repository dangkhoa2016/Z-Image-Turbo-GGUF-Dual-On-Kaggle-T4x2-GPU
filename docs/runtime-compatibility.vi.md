# Tương thích môi trường và hướng dẫn khởi chạy

> 🌐 Language / Ngôn ngữ: [English](runtime-compatibility.md) | **Tiếng Việt**

## Môi trường tham chiếu đã kiểm chứng

Z-Image-Turbo GGUF Q6_K đã chạy thực tế trên **Kaggle Tesla T4 ×2**, với giai đoạn mã hóa prompt có giới hạn trên GPU0 và worker inference độc lập ở GPU0/GPU1. Nghiệm thu đầu-cuối trước đây bao gồm gửi prompt từ trình duyệt đã xác thực, nhận PNG 1024 × 1024, kiểm tra SHA256 và View/Download. Xem chỉ mục bằng chứng để biết chính xác phạm vi từng lần xác minh.

## Khởi chạy trên Kaggle

1. Chọn **GPU T4 ×2** và bật Internet cho lần chuẩn bị môi trường đầu tiên.
2. Attach model GGUF `dangkhoa2016/unsloth-z-image-turbo-gguf`, biến thể `q6-k`, phiên bản 1, và dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`.
3. Mở notebook trình diễn. Chạy tuần tự để kiểm tra dữ liệu, khởi động API/Studio và GPU consumer rồi mở hai website HTTPS.
4. Đăng nhập bằng tài khoản demo được tạo trong notebook, nhập prompt, kiểm tra job, artifact và tải ảnh. Để minh họa dual inference, kiểm tra hai GPU với các job riêng.

## Tương thích runtime

Repo chứa mã nguồn và notebook khởi chạy, không phân phối weights, artifact riêng tư hay SQLite runtime. Môi trường mới cần phiên bản GPU/PyTorch/Diffusers/Transformers tương thích và dữ liệu model tương ứng. Runtime Kaggle trước đã PASS các bài kiểm tra được lưu; **mỗi phiên Kaggle mới vẫn cần chạy kiểm chứng riêng trước khi đánh dấu là đã xác minh**. GitHub CI chỉ kiểm tra cấu trúc và cú pháp, không thực thi GPU inference.

## Xem thêm

[Cấu hình trình diễn](deployment-profile.vi.md) · [Kiến trúc](architecture.vi.md) · [Hướng dẫn Kaggle](kaggle.vi.md) · Bằng chứng kỹ thuật
