# Z-Image-Turbo GGUF Q6_K — v1.0.0

**Bản phát hành công khai đầu tiên · Tạo ảnh AI bằng hai GPU Tesla T4 trên Kaggle**

**Ngôn ngữ:** [English](RELEASE_NOTES_v1.0.0.md) · Tiếng Việt

Bản phát hành này giới thiệu một hệ thống demo mã nguồn mở, hoàn chỉnh theo quy trình đầu-cuối, sử dụng **Z-Image-Turbo GGUF Q6_K trên hai GPU NVIDIA Tesla T4**. Dự án kết hợp chuẩn bị mô hình có kiểm soát tài nguyên GPU, hai worker tạo ảnh độc lập, notebook Kaggle có hướng dẫn, Vue Studio có xác thực và hai gallery có thể duyệt với **170 ảnh được đóng watermark**.

Mục tiêu không chỉ là nạp được mô hình lượng tử hóa hoặc trưng bày một vài ảnh sinh ra. Dự án hướng đến một quy trình dual-GPU **dễ hiểu, có thể thực thi, quan sát và kiểm chứng**: từ xác minh input, mã hóa prompt có giới hạn, tạo ảnh trên từng GPU đến quản lý vòng đời tác vụ, sử dụng qua trình duyệt và lưu bằng chứng có thể đối chiếu.

**Khám phá bản phát hành:** [Bộ ảnh minh họa](#bộ-ảnh-minh-họa) · [Tính năng chính](#những-gì-có-trong-bản-phát-hành) · [Kiến trúc](#hệ-thống-hoạt-động-thế-nào) · [Trạng thái nghiệm thu](#trạng-thái-nghiệm-thu-gpu-của-bản-phát-hành) · [Chạy trên Kaggle](#chạy-demo-trên-kaggle) · [Tệp phát hành](#tệp-tải-về-và-kiểm-tra-toàn-vẹn)

## Bộ ảnh minh họa

| Ảnh tuyển chọn 010 | Ảnh tuyển chọn 011 | Ảnh tuyển chọn 013 | Ảnh tuyển chọn 027 |
| :---: | :---: | :---: | :---: |
| ![Ảnh minh họa đã phát hành 010](assets/showcase/pqt_v1_010.webp) | ![Ảnh minh họa đã phát hành 011](assets/showcase/pqt_v1_011.webp) | ![Ảnh minh họa đã phát hành 013](assets/showcase/pqt_v1_013.webp) | ![Ảnh minh họa đã phát hành 027](assets/showcase/pqt_v1_027.webp) |

*Đây là các ảnh xem trước dung lượng nhỏ từ gallery chất lượng đã phát hành và có watermark; không phải hai ảnh PNG riêng dùng để chứng minh lần chạy GPU. [Gói gallery đầy đủ 170 ảnh](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz) còn chứa giao diện duyệt và metadata đi kèm.*

## Những gì có trong bản phát hành

**Một quy trình demo hoàn chỉnh, không chỉ là script nạp mô hình.** Bản phát hành đầu tiên gồm năm thành phần có thể trải nghiệm cùng nhau hoặc xem xét riêng:

1. **GGUF inference trên hai GPU.** Bước mã hóa prompt được giới hạn trên GPU 0; sau đó hai inference worker riêng tạo ảnh trên **GPU 0 và GPU 1**. GPU 0 tham gia cả hai giai đoạn, chứ không chỉ dành riêng cho text encoder.
2. **Notebook Kaggle lấy source trực tiếp từ GitHub.** Notebook **28 cell**, gồm **12 code cell ngắn và 16 cell hướng dẫn song ngữ**, kiểm tra hai input Kaggle, chuẩn bị runtime và thực hiện tạo ảnh mà không cần thêm dataset Kaggle chỉ để chứa mã nguồn.
3. **Studio tạo ảnh tương tác.** Giao diện Vue cho phép đăng nhập, gửi prompt, theo dõi hàng đợi dựa trên SQLite, xem trạng thái tác vụ, mở và tải ảnh, đồng thời phân biệt thời gian vòng đời tác vụ với thời gian xử lý trên GPU.
4. **Bộ sưu tập ảnh có thể kiểm tra.** Hai gallery song ngữ gồm **48 ảnh tuyển chọn** và **122 ảnh thử nghiệm/benchmark**, kèm prompt và metadata trong phạm vi có sẵn. Gói phát hành riêng chứa **170 PNG có watermark và 40 thumbnail WebP**.
5. **Tài liệu và bằng chứng kỹ thuật.** Dự án công bố số liệu runtime, thông tin phiên bản source đã thử, kiểm tra ảnh bằng SHA256, CPU tests, các ranh giới bảo mật, thiết kế hệ thống và hướng dẫn Kaggle để người khác có thể review.

Dự án dành cho **kỹ sư AI/ML, lập trình viên nghiên cứu tạo ảnh bằng GGUF và người dùng Kaggle** muốn tìm hiểu cách tổ chức và kiểm tra một quy trình inference gồm nhiều thành phần.

## Hệ thống hoạt động thế nào

Kiến trúc tách biệt giao diện tương tác, quản lý hàng đợi, mã hóa prompt, inference tạo ảnh và gallery công khai. Gateway Studio phục vụ trình duyệt cũng được tách khỏi API xử lý ảnh nội bộ.

~~~text
Notebook Kaggle → source GitHub + model/support inputs đã xác minh
        │
        ├─ Kiểm tra GPU, dependency, dung lượng và tính toàn vẹn model
        │
        └─ Mã hóa prompt Qwen3 (giai đoạn giới hạn trên GPU 0)
                          │
                    Phân phối tác vụ
                    /           \
       GGUF worker GPU 0       GGUF worker GPU 1
                    \           /
                    PNG 1024×1024
                          │
                 Kiểm tra SHA256
                          │
         Bằng chứng notebook + ảnh trong Studio

Trình duyệt → Vue Studio có xác thực → API riêng tư
                                        │
                                 SQLite job/session queue
                                        │
                                     GPU workers

Trình duyệt → hai gallery quality/benchmark trên server riêng
~~~

Cách tổ chức này đặc biệt có ý nghĩa trên GPU Tesla T4: chuẩn bị encoder và GGUF weights, kiểm soát áp lực bộ nhớ, giao tác vụ thực sự cho cả hai GPU và xác minh tệp kết quả là **những bài toán độc lập**. Repo không coi việc phát hiện hai GPU là bằng chứng đủ để kết luận inference song song hữu ích đã diễn ra.

**Thiết kế Studio.** Trình duyệt kết nối đến gateway có xác thực (cổng **18789**), còn API (cổng **18788**) được giữ riêng tư. SQLite quản lý trạng thái job và session; ảnh hoàn tất gắn với job và quyền sở hữu tương ứng, có receipt riêng và cơ chế tải ảnh qua xác thực. Hai gallery công khai dùng server tĩnh độc lập, không phơi bày ảnh riêng tư của Studio.

**Tính toàn vẹn của model và source.** Quy trình xác minh Git revision được checkout, staging các thành phần GGUF/encoder có kiểm tra hash. Notebook cũng phân biệt ảnh vừa được sinh trong lần thực thi hiện tại với ảnh cũ chỉ được xác minh checksum. Đây là điểm quan trọng khi đánh giá cả hai GPU có thực sự chạy inference hay không.

Xem thêm [Kiến trúc](docs/architecture.vi.md), [API và Studio](docs/api.vi.md), [Tương thích runtime](docs/runtime-compatibility.vi.md).

## Những lựa chọn thiết kế và giá trị kỹ thuật

Bản phát hành v1.0.0 không chỉ minh họa việc nhận diện hai GPU. Dự án kết hợp nhiều bước riêng biệt thành một quy trình tạo ảnh có thể quan sát và nghiên cứu: chuẩn bị mô hình, mã hóa prompt, phân phối tác vụ, quản lý kết quả và hiển thị ảnh.

| Bài toán | Thiết kế được sử dụng | Lợi ích đối với người nghiên cứu |
| --- | --- | --- |
| **Mô hình gồm nhiều thành phần** | GGUF Q6_K và bộ text encoder/tokenizer/VAE được gắn qua hai Kaggle input riêng. Các tệp cần thiết được chuẩn bị và kiểm tra tính toàn vẹn trước inference. | Phân biệt được chi phí chuẩn bị mô hình với thời gian sinh ảnh, đồng thời giảm sự mơ hồ về nguồn dữ liệu đầu vào. |
| **Chia sẻ tài nguyên GPU 0** | Giai đoạn mã hóa prompt bằng Qwen3 được giới hạn trên GPU 0; tiếp đó cả GPU 0 và GPU 1 chạy các worker tạo ảnh GGUF độc lập. | GPU 0 không chỉ làm nhiệm vụ encoder; cả hai thiết bị đều tham gia tạo ảnh với vai trò và giai đoạn được thể hiện rõ ràng. |
| **Hai tác vụ chạy đồng thời** | Hai worker riêng có thông tin thời gian và kết quả theo thiết bị; Studio theo dõi vòng đời hàng đợi và phiên xử lý. | Có thể đánh giá công việc thực tế của từng GPU mà không nhầm lẫn giữa xử lý song song và tăng tốc cho riêng một ảnh. |
| **Tách biệt trải nghiệm tương tác** | Vue Studio dùng gateway có xác thực, API ứng dụng và cơ sở dữ liệu SQLite cho tác vụ; hai gallery ảnh được phục vụ độc lập. | Dễ phân biệt quy trình tạo ảnh theo phiên với bộ ảnh mẫu đã công bố để cộng đồng tham khảo. |
| **Truy xuất nguồn gốc** | Notebook lấy mã nguồn từ GitHub, ghi nhận revision và checksum, đồng thời phân biệt ảnh vừa sinh ra với tệp được tái sử dụng. | Kết quả có thể được đối chiếu với mã nguồn và artifact cụ thể thay vì chỉ dựa trên thông báo chạy thành công. |

Những quyết định này cũng giải thích vì sao dự án phân tách **model staging, chuẩn bị encoder, khởi tạo GPU worker, render ảnh và cung cấp kết quả qua trình duyệt**. I/O lưu trữ, khởi tạo VAE và tài nguyên Kaggle có thể khác nhau theo phiên, nên các kết quả được giới thiệu đúng phạm vi quan sát. Số liệu chi tiết và phương pháp đánh giá được trình bày riêng trong [tài liệu benchmark](docs/benchmark.vi.md) và [chỉ mục bằng chứng](docs/evidence-index.vi.md).

Nhờ vậy, người đọc có thể nghiên cứu không chỉ cách sinh ảnh mà còn cách tổ chức một demo inference nhiều thành phần trong giới hạn tài nguyên GPU thực tế.

## Nghiệm thu GPU và hồ sơ kiểm chứng

**Kiểm chứng và tái lập:** Bản phát hành v1.0.0 cung cấp quy trình Kaggle Tesla T4 ×2 có thể truy vết mã nguồn và kiểm tra tính toàn vẹn kết quả. GPU inference, thao tác Studio có xác thực và khả năng tái lập độc lập được đánh giá riêng, dựa trên bằng chứng gắn với Git SHA thực tế. Xem [GitHub Release v1.0.0](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/tag/v1.0.0) để đối chiếu kết quả và artifacts đã công bố.

Mỗi phiên GPU được nghiệm thu phải ghi Git SHA thực tế, hai PNG 1024 × 1024 sinh mới (mỗi GPU một ảnh), SHA256 độc lập, thông tin worker và thời gian render, kèm biên nhận. Studio tạo ảnh, View/Download trên browser và hai gallery cần được kiểm riêng.

[Quy trình nghiệm thu theo revision](docs/evidence-index.vi.md) mô tả bằng chứng bắt buộc. Không dùng kết quả các phiên phát triển trước làm chứng nhận notebook hoặc source SHA mới.

## Hai gallery ảnh bổ trợ cho nhau

| Bộ sưu tập | Nội dung có thể khám phá |
| --- | --- |
| **Quality gallery — 48 ảnh** | Ảnh minh họa tuyển chọn, thông tin review, quan hệ giữa ảnh gốc và ảnh render lại cùng metadata trạng thái nếu có. |
| **Test & benchmark gallery — 122 ảnh** | Tập kết quả tạo ảnh rộng hơn, với thông tin prompt, runtime, GPU worker và tệp đầu ra trong phạm vi dữ liệu được lưu. |

Cả hai gallery đều có giao diện **tiếng Anh/tiếng Việt**, xem chi tiết, điều hướng và các công cụ duyệt ảnh. Archive phát hành chứa tổng cộng **170 PNG có watermark**; **40 thumbnail WebP** chỉ là ảnh dẫn xuất tối ưu cho trình duyệt, *không phải 40 ảnh sinh thêm*. Ảnh gốc không watermark và tệp riêng của Studio không được phân phối công khai.

Có thể xem gallery **mà không cần cấp phát GPU Kaggle**: tải archive, giải nén và phục vụ/mở các tệp gallery tĩnh đi kèm. Xem [hướng dẫn gallery trong README](README.vi.md#hai-gallery-170-ảnh-trên-release) để biết cách làm và kiểm tra checksum.

Việc người vận hành đã xem các ảnh không đồng nghĩa có bằng chứng độc lập rằng mọi ảnh đều tuân thủ prompt hoàn hảo. Metadata gallery giữ ranh giới giữa kết quả demo và đánh giá chất lượng ảnh.

## Chạy demo trên Kaggle

### Yêu cầu

Cần một notebook Kaggle với **NVIDIA Tesla T4 ×2**, **bật Internet**, có đủ tài nguyên runtime và attach *cả hai* input sau:

| Loại input | Tài nguyên cần gắn |
| --- | --- |
| **Kaggle Model** | [dangkhoa2016/unsloth-z-image-turbo-gguf](https://www.kaggle.com/models/dangkhoa2016/unsloth-z-image-turbo-gguf/gguf/q6-k) — framework **gguf**, variation **q6-k**, version **1** |
| **Kaggle Dataset** | [z-image-turbo-diffusers-support-components](https://www.kaggle.com/datasets/dangkhoa2016/z-image-turbo-diffusers-support-components) — text encoder, tokenizer và VAE |

**Model** chứa GGUF Q6_K weights; **Dataset** riêng chứa những thành phần Diffusers hỗ trợ cần thiết. Hai input này không phải dataset chứa mã nguồn GitHub của ứng dụng.

### Hướng dẫn năm bước

1. **Tải và import** [notebook 28 cell chính thức từ Release](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb) vào Kaggle. Đây là notebook mẫu không lưu output, không phải bản dump các log thực thi riêng tư.
2. **Cấu hình session:** chọn accelerator **Tesla T4 ×2**, bật Internet; tại **Input → Add Input**, attach chính xác Model và Dataset nêu trên.
3. **Chạy notebook theo thứ tự.** Notebook kiểm tra GPU và input, lấy source từ GitHub, chuẩn bị dependency, mã hóa prompt rồi phân phối tác vụ tạo ảnh cho từng GPU. Không cần sửa code cell để chạy cấu hình được hướng dẫn.
4. **Kiểm tra kết quả:** đối chiếu hai PNG **1024 × 1024** mới sinh, kiểm tra hash và lưu evidence ZIP. Khi đánh giá một lần chạy mới, phân biệt ảnh *được sinh trong lượt này* với output cũ được tái sử dụng.
5. **Thử giao diện web tùy chọn:** mở Studio và các gallery theo URL riêng được in trong session, dùng thông tin đăng nhập Studio tạm thời của bạn, gửi prompt và tải ảnh hoàn tất. Ngắt cell monitor liên tục khi kết thúc, lưu những tệp cần thiết trước khi Kaggle runtime đóng.

[Hướng dẫn Kaggle từng bước](docs/public-demo-notebook.vi.md) mô tả cách chọn model, đường dẫn input, từng giai đoạn chạy, dấu hiệu đầu ra mong đợi và cách xử lý lỗi. Notebook Kaggle đã thực thi của người vận hành vẫn được chủ động giữ **PRIVATE**, không phải điểm truy cập `Copy & Edit` công khai. Hãy import notebook sạch từ GitHub Release này; khả năng tái hiện GPU bằng tài khoản độc lập chưa được xác minh.

## Tệp tải về và kiểm tra toàn vẹn

**v1.0.0** có ba asset. Git repository cố ý không chứa model weights dung lượng lớn, ảnh riêng tư đã tạo hoặc runtime databases.

| Tệp tải về | Nội dung | Kích thước |
| --- | --- | ---: |
| [**Notebook demo Kaggle** (.ipynb)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/kaggle-dual-gpu-production-demo.ipynb) | Notebook mẫu 28 cell có hướng dẫn, không lưu output | 53.176 byte |
| [**Gallery công khai 170 ảnh** (.tar.gz)](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/releases/download/v1.0.0/zimage-gallery-170-watermarked-public-v1.0.0.tar.gz) | Ảnh watermark, thumbnail WebP và gallery song ngữ | 228.277.211 byte |

**SHA256 của hai asset ổn định:**

~~~text
d925b1f3b729d5ea4ca6cc655b14eb90eced42dd4a11e9e8ca6cbd98f1f9d094  kaggle-dual-gpu-production-demo.ipynb
acb2997ac8430ba239d8afadcfb8d17c7ff09634e00299f3bf8d2161681b207e  zimage-gallery-170-watermarked-public-v1.0.0.tar.gz
~~~

SHA256 và kích thước của hai asset có trong GitHub Release metadata. Model weights cần attach từ Kaggle theo license upstream.

## Tương thích, phạm vi và bảo mật

- **Môi trường đã thử:** Kaggle **Tesla T4 ×2**. Runtime CPU-only hoặc chỉ có một T4 không nằm trong cấu hình hỗ trợ của quy trình dual-GPU này.
- **Phạm vi hiệu năng:** Thời gian render GPU, nếu được nghiệm thu, sẽ công bố trong báo cáo trên GitHub Release. Hai worker không bảo đảm một ảnh được tạo nhanh gấp đôi, thời gian cold-start cố định hay throughput áp dụng mọi máy.
- **Thời hạn session:** Bộ nhớ lưu trữ runtime, trạng thái Studio, kết quả chưa tải về và Cloudflare Quick Tunnel URL có thể chỉ tồn tại tạm thời. Studio là **demo theo phiên**, không phải dịch vụ vận hành liên tục.
- **Ranh giới bảo mật:** Chỉ public gateway Studio có xác thực; API riêng, receipt, service token và thông tin đăng nhập đang hoạt động phải được bảo vệ. Không công khai notebook đã execute khi output còn chứa mật khẩu hoặc tunnel URL có hiệu lực.
- **Ranh giới tái hiện:** GPU inference và thao tác browser phải được chứng minh bằng evidence trên GitHub Release cho đúng Git SHA. Việc Copy & Edit từ tài khoản độc lập và kiểm tra output đã làm sạch cần bằng chứng riêng; mỗi phiên phải xác minh inputs và kết quả.

## Tìm hiểu mã nguồn và đóng góp

| Chủ đề | Nơi bắt đầu |
| --- | --- |
| Tổng quan dự án và gallery | [README tiếng Việt](README.vi.md) |
| Quy trình notebook | [notebooks/](notebooks/) và [hướng dẫn Kaggle](docs/public-demo-notebook.vi.md) |
| Inference, queue, artifact | [production-system/](production-system/) |
| Vue Studio và gateway | [product-studio/](product-studio/) |
| Kiến trúc và API Studio | [Kiến trúc](docs/architecture.vi.md) · [API](docs/api.vi.md) |
| Runtime và dependency | [Tương thích](docs/runtime-compatibility.vi.md) · [Dependency](docs/vendor-dependencies.vi.md) |
| Kết quả và phương pháp đo | [Chỉ mục bằng chứng](docs/evidence-index.vi.md) · [Benchmark](docs/benchmark.vi.md) |
| Kiểm tra repository | [GitHub Actions audit](https://github.com/dangkhoa2016/Z-Image-Turbo-GGUF-Dual-On-Kaggle-T4x2-GPU/actions/workflows/repository-audit.yml) |

Mã nguồn và tài liệu do dự án phát triển được phát hành theo **Giấy phép MIT**, bản quyền © 2026 **Đăng Khoa**. **Model weights và package của bên thứ ba không được cấp lại giấy phép chỉ vì repo này sử dụng MIT**; xem [Ghi chú giấy phép](LICENSE-NOTES.vi.md), [giấy phép upstream](THIRD_PARTY_LICENSES/Z-IMAGE-APACHE-2.0) và [dự án Z-Image gốc](https://github.com/Tongyi-MAI/Z-Image).

Dự án đón nhận issue, review kỹ thuật và pull request có phạm vi rõ ràng. Hãy đọc [Hướng dẫn đóng góp](CONTRIBUTING.vi.md) và [Chính sách bảo mật](SECURITY.vi.md) trước khi gửi báo lỗi hoặc log tái hiện. Không đưa credential, ảnh riêng tư hay tunnel URL đang hoạt động vào nội dung công khai.
