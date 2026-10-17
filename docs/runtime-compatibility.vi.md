# Tương thích môi trường và hướng dẫn khởi chạy

> 🌐 Language / Ngôn ngữ: [English](runtime-compatibility.md) | **Tiếng Việt**

## Môi trường tham chiếu đã kiểm chứng

Z-Image-Turbo GGUF Q6_K đã chạy thực tế trên **Kaggle Tesla T4 ×2**, với giai đoạn mã hóa prompt có giới hạn trên GPU0 và worker inference độc lập ở GPU0/GPU1. Nghiệm thu đầu-cuối trước đây bao gồm gửi prompt từ trình duyệt đã xác thực, nhận PNG 1024 × 1024, kiểm tra SHA256 và View/Download. Xem [chỉ mục bằng chứng](evidence-index.vi.md) để biết chính xác phạm vi từng lần xác minh.

## Khởi chạy trên Kaggle

1. Chọn **GPU T4 ×2** và bật Internet cho lần chuẩn bị môi trường đầu tiên.
2. Attach model GGUF `dangkhoa2016/unsloth-z-image-turbo-gguf`, biến thể `q6-k`, phiên bản 1, và dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`.
3. Mở [notebook trình diễn](../notebooks/kaggle-dual-gpu-production-demo.ipynb). Chạy tuần tự để kiểm tra dữ liệu, khởi động API/Studio và GPU consumer rồi mở hai website HTTPS.
4. Đăng nhập bằng tài khoản demo được tạo trong notebook, nhập prompt, kiểm tra job, artifact và tải ảnh. Để minh họa dual inference, kiểm tra hai GPU với các job riêng.

## Tương thích runtime

Repo chứa mã nguồn và notebook khởi chạy, không phân phối weights, artifact riêng tư hay SQLite runtime. Môi trường mới cần phiên bản GPU/PyTorch/Diffusers/Transformers tương thích và dữ liệu model tương ứng. Runtime Kaggle trước đã PASS các bài kiểm tra được lưu; **mỗi phiên Kaggle mới vẫn cần chạy kiểm chứng riêng trước khi đánh dấu là đã xác minh**. GitHub CI kiểm tra cấu trúc và cú pháp, đồng thời chạy bộ kiểm thử hợp đồng/bảo mật trên CPU (`requirements-ci.txt` + `python scripts/run_cpu_tests.py`); CI không thực thi GPU inference.

## Khoá phụ thuộc runtime

Lock dạng máy đọc được nằm tại [`manifests/runtime-compatibility.json`](../manifests/runtime-compatibility.json).

- **Đã xác minh trên CPU:** bốn wheel vendor khoá SHA256 — Diffusers 0.41.0,
  Hugging Face Hub 1.28.0, TorchAO 0.15.0, GGUF 0.17.1 — kèm hash wheel,
  cây giải nén và dist-info, cùng bộ tham chiếu CPU/CI trong
  [`requirements-ci.txt`](../requirements-ci.txt).
- **Cần kiểm tra trên GPU:** xác minh phiên bản PyTorch, CUDA, Transformers, Accelerate và Python ngay trên môi trường T4 ×2 thực tế trước khi công bố kết quả tương thích.
- `requirements.txt` vẫn là bộ tối thiểu không ghim phiên bản, nay có thêm
  `numpy` vì `safetensors.torch.save_file` cần nó lúc chạy (`encode_batch_gpu.py`,
  `encode_batch_cpu_mock.py`). Không tự nâng PyTorch trên runtime GPU đã được
  chấp nhận khi chưa có bằng chứng tương thích.

## Chính sách checkout nguồn

Notebook demo lấy bản làm việc qua `scripts/source_checkout.py`, cơ chế fail-closed:
từ chối ghi đè thư mục không rỗng (`SOURCE_TREE_DIRTY`), remote bất thường, hoặc
revision không khớp (`SOURCE_SHA_MISMATCH`), và không bao giờ chạy `git reset --hard`.
Một phiên Kaggle mới nên dùng commit SHA hoặc release tag được công bố và xác minh.

## Kiểm chứng

Chạy bộ test CPU bằng `python scripts/run_cpu_tests.py`. Các phép thử GPU và trình duyệt cần được thực hiện trên phiên Kaggle hiện tại trước khi sử dụng kết quả đó như bằng chứng nghiệm thu.

## Xem thêm

[Cấu hình trình diễn](deployment-profile.vi.md) · [Kiến trúc](architecture.vi.md) · [Hướng dẫn Kaggle](kaggle.vi.md) · [Bằng chứng kỹ thuật](evidence-index.vi.md)
