# Phụ thuộc vendor có thể tái lập (bản preview)

GitHub repository là nguồn source code chính. Trên Kaggle, notebook clone repository rồi chạy `python3 scripts/bootstrap_vendor.py`. Script tải wheel upstream đã khóa SHA256 từ PyPI (cần Internet) hoặc sử dụng wheel tải sẵn qua `--wheel-dir PATH`. Script xác minh SHA256 wheel, cây file thư viện và metadata phân phối chứa giấy phép. Không còn dùng Git archive branch trong notebook preview.

Các phiên bản đã đối chiếu: Diffusers 0.41.0 (Apache-2.0), Hugging Face Hub 1.28.0 (Apache-2.0), TorchAO 0.15.0 (BSD-3-Clause), GGUF 0.17.1 (MIT). `vendor-shim/sitecustomize.py` là phần tương thích riêng của dự án. Các thư mục vendor giải nén là output runtime, **không được commit như source MIT của dự án**.

Wheel TorchAO phụ thuộc nền tảng; bản đã đối chiếu là Linux x86_64 cp310-abi3, không phải đảm bảo chạy trên mọi hệ thống. Việc đọc phiên bản bằng `importlib.metadata` phải nhắm vào đường dẫn phân phối vendored, không chỉ đọc thư viện được cài sẵn.

GGUF model weights và text-encoder/VAE là model data riêng, không thuộc repository source. Technical Preview chưa sẵn sàng production. Vẫn cần khóa các runtime dependencies khác, kiểm thử fresh clone từ candidate đã xuất bản, kiểm thử GPU T4x2 và browser E2E.

[Tiếng Việt](vendor-dependencies.vi.md) · [English](vendor-dependencies.md)

**Giới hạn kiểm chứng:** Chưa xác minh phiên bản PyTorch, Transformers, Accelerate của runtime T4×2 cũ; không được tự dùng phiên bản của máy CPU hiện tại làm lock GPU. GPU preflight và worker phải vượt qua xác minh vendor trước khi hoạt động.
