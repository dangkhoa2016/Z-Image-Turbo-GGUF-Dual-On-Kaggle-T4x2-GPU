# Chạy Z-Image Turbo Q6_K trên Kaggle T4 ×2

> 🌐 Language / Ngôn ngữ: [English](public-demo-notebook.md) | **Tiếng Việt**

## Bắt đầu tại đây — chỉ chọn một notebook

**Bạn chỉ cần import [kaggle-dual-gpu-production-demo.ipynb](../notebooks/kaggle-dual-gpu-production-demo.ipynb).** Đây là notebook chính dành cho cộng đồng, phục vụ tạo ảnh và trải nghiệm Studio/Gallery. Notebook gồm 16 cell hướng dẫn đầy đủ bằng tiếng Anh/Việt và 12 code cell ngắn.

Hãy tải notebook được liên kết, gắn Model và Dataset theo hướng dẫn bên dưới, rồi chạy trên Kaggle.

**Kết quả nhận được:** Hai ảnh PNG **1024 × 1024** tạo mới từ hai GPU Tesla T4, SHA256, file ZIP bằng chứng, Studio đăng nhập tạm thời và hai thư viện ảnh mẫu. Mã nguồn ứng dụng được tải trực tiếp từ **GitHub**, không thông qua Kaggle Dataset chứa source.

## A. Import notebook vào Kaggle

1. Mở [notebook chính thức](../notebooks/kaggle-dual-gpu-production-demo.ipynb) trên GitHub.
2. Tải **file `.ipynb` gốc** bằng chức năng **Download raw file**, không tải trang HTML hiển thị notebook.
3. Đăng nhập [Kaggle](https://www.kaggle.com/), vào trình soạn thảo **Notebooks** và import/upload file `.ipynb` vừa tải. Tên mục import có thể khác nhau giữa các phiên bản giao diện.
4. Mở **Session options / Notebook settings**, chọn **Accelerator → GPU T4 ×2** và bật **Internet**.
5. Nên bắt đầu phiên Kaggle mới, chưa có model hoặc tác vụ GPU khác đang chạy. Notebook tự kiểm tra đủ hai GPU.

**Lưu ý:** Notebook được xây dựng cho **hai Tesla T4**. Chọn CPU hoặc chỉ một T4 không đáp ứng yêu cầu đã kiểm thử của dự án.

## B. Gắn GGUF Q6_K — chọn mục **Models**, không phải Datasets

Nguồn đầu tiên là một **Kaggle Model**. Bạn cần gắn model này vào notebook; không thay bằng checkpoint GGUF có quantization khác.

1. Tại Kaggle Notebook editor, tìm panel **Input** ở bên phải. Nhấn **Add Input** hoặc **Add Models** (tên nút tùy bố cục).
2. Chuyển sang danh mục/bộ lọc **Models**, **không phải Datasets**.
3. Tìm theo tên đầy đủ `dangkhoa2016/unsloth-z-image-turbo-gguf` hoặc mở [trang model trên Kaggle](https://www.kaggle.com/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k) để đối chiếu.
4. Xác nhận **owner:** `dangkhoa2016`; **model:** `unsloth-z-image-turbo-gguf`.
5. Trong hộp chọn model, chọn **framework:** `gguf`; **variation:** `q6-k`; **version:** `1`. Cần đúng cả ba trường; không chọn biến thể lượng tử hay phiên bản khác.
6. Chọn **Add / Attach** để gắn vào notebook hiện tại. Nếu được yêu cầu chấp nhận giấy phép, hãy đọc và chỉ đồng ý nếu phù hợp.

**Kiểm tra:** Panel Input cần hiển thị model `gguf / q6-k / 1`. File trọng số dự kiến là `z-image-turbo-Q6_K.gguf`. Notebook sẽ tự xác minh đường dẫn Kaggle thực tế khi chạy.

## C. Gắn thành phần hỗ trợ — chọn mục **Datasets**, không phải Models

Nguồn thứ hai là một **Kaggle Dataset** lưu các thành phần hỗ trợ cho model GGUF.

1. Quay lại **Input → Add Input**.
2. Chuyển sang danh mục/bộ lọc **Datasets**, không chọn Models.
3. Tìm `dangkhoa2016/z-image-turbo-diffusers-support-components` hoặc mở [trang support dataset](https://www.kaggle.com/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components).
4. Xác nhận **owner:** `dangkhoa2016`; **dataset:** `z-image-turbo-diffusers-support-components`, rồi nhấn **Add / Attach**.
5. Nhìn lại panel **Input**: bạn cần thấy **cả model GGUF Q6_K lẫn support dataset**. Thiếu một trong hai thì chưa thể chạy Run All.

**Vì sao cần dataset?** Dataset này chứa các thư mục **text_encoder**, **tokenizer** và **vae**. Nó **không chứa trọng số GGUF chính**, cũng **không phải dataset chứa mã nguồn** của repository.

### Bảng kiểm hai nguồn dữ liệu

| Loại | Lựa chọn chính xác | Đường dẫn Kaggle cần có |
| --- | --- | --- |
| **Model** | `dangkhoa2016/unsloth-z-image-turbo-gguf` → `gguf / q6-k / 1` | `/kaggle/input/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k/1/z-image-turbo-Q6_K.gguf` |
| **Dataset** | `dangkhoa2016/z-image-turbo-diffusers-support-components` | `/kaggle/input/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components/z-image-turbo-diffusers-support` |

Đây là **đường dẫn mà code đang kiểm tra**, không phải đường dẫn bạn cần gõ thủ công. Notebook sẽ báo lỗi rõ ràng nếu thiếu file, sai version hoặc thư mục support không hợp lệ. Không tự di chuyển hay đổi tên các file Kaggle đã attach.

## D. Chạy Run All và nhận biết kết quả

Sau khi gắn đủ hai nguồn, chọn **Run All**. **Không cần sửa code cell** nào.

| Các bước | Notebook thực hiện | Dấu hiệu thành công |
| --- | --- | --- |
| Source và môi trường | Kiểm Git SHA, hai GPU, model/dataset, cài thư viện | `SOURCE_READY`, `GPU_T4X2_READY`, `PREFLIGHT_READY` |
| Mã hóa prompt | Tạo embedding cho hai prompt | `NOTEBOOK_GPU_EMBEDDINGS_READY` |
| Sinh ảnh bằng GPU | Nạp worker GPU0/GPU1, sinh hai ảnh mới | `BOTH_MODEL_INSTANCES_READY`, hai PNG 1024 × 1024 hợp lệ |
| Kiểm chứng và đóng gói | Kiểm SHA256, provenance, tạo ZIP | `NOTEBOOK_OWN_INFERENCE_PROOF: PASS`, `p23-runall-acceptance.zip` |
| Studio và Gallery | Khởi động webserver, tạo link HTTPS tạm | Trang đăng nhập Studio và hai link gallery |
| Monitor | Hiển thị trạng thái job, GPU và log liên tục | Dùng **Interrupt Cell** sau khi thử xong |

Để chứng minh **Fresh Run All**, cần trạng thái `GENERATED_IN_CURRENT_RUN`. Ảnh tái sử dụng có SHA256 hợp lệ vẫn **không chứng minh** lần chạy mới vừa sinh ảnh.

## E. Thử Studio và hai gallery

1. Mở URL Studio HTTPS mà notebook in ra; dùng username `studio` và mật khẩu tạm từ output Kaggle **của bạn**.
2. Nhập một **prompt mới** và submit. Theo dõi hàng đợi, tiến độ GPU và log trong cell monitor cuối.
3. Sau khi tạo được PNG mới, thử **View** và **Download**, đồng thời kiểm session/job có trạng thái hoàn tất `ARCHIVED`.
4. Mở cả **Quality Gallery** và **Benchmark Gallery**; xác nhận ảnh hiển thị, có thể xem và điều hướng giữa hai trang.
5. Nếu notebook báo `PENDING_BROWSER_VERIFICATION`, nghĩa là bước kiểm HTTPS **chưa được xác nhận từ Kaggle**. Bạn phải mở trực tiếp link bằng trình duyệt; không được coi pending là PASS.
6. Lưu ảnh PNG, SHA256, ZIP và notebook đã chạy trước khi Kaggle kết thúc phiên. Tuyệt đối không công khai mật khẩu Studio còn hiệu lực.

Việc Studio sinh ảnh mới **tách biệt** với hai ảnh được tạo trực tiếp trong notebook. Hai PNG notebook PASS không tự động chứng minh browser Studio E2E PASS.

## Cách xử lý những lỗi phổ biến

| Vấn đề | Điều cần kiểm tra |
| --- | --- |
| Không tìm thấy model | Đang lọc **Models** chưa? Owner là `dangkhoa2016`? Có đúng `gguf / q6-k / 1` không? |
| Không tìm thấy support | Chuyển sang **Datasets** và attach thêm `z-image-turbo-diffusers-support-components` |
| Notebook báo không có T4 ×2 | Chọn đúng Accelerator trong Session options, T4 đơn lẻ không đủ |
| Không clone được source | Kiểm Internet và quyền truy cập GitHub |
| Không đủ dung lượng | Notebook tự quản lý staging và kiểm dung lượng; hãy lưu dữ liệu hiện có và dùng phiên sạch, không vô hiệu hóa cơ chế an toàn |
| Mở Studio được nhưng không có ảnh | Giữ monitor chạy, lưu log consumer/encoder/worker, xác minh job mới đạt `ARCHIVED` |

Để xem cách **Input → Add Input** hoạt động theo giao diện Kaggle, tham khảo [tài liệu Notebook chính thức](https://www.kaggle.com/docs/notebooks). Cách chọn **framework, variation, version** được giải thích trong [tài liệu Kaggle Models](https://www.kaggle.com/docs/models). Tên nút có thể thay đổi theo bố cục nhưng chức năng tương đương.

## Nghiệm thu theo Git revision

Notebook production lấy source từ **`main`** và ghi nhận đúng Git SHA lúc chạy. Để tái lập kết quả, đặt `ZIMAGE_SOURCE_SHA` theo SHA được công bố trên [GitHub Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) và kiểm đầu ra notebook khớp SHA này. [Quy trình nghiệm thu](evidence-index.vi.md) quy định evidence cần có; tái lập bằng tài khoản khác phải được chứng minh riêng.
