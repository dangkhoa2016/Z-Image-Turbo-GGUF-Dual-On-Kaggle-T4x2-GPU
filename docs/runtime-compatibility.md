# Runtime Compatibility & Launch Guide

> 🌐 Language / Ngôn ngữ: **English** | [Tiếng Việt](runtime-compatibility.vi.md)

## Validated reference environment

Z-Image-Turbo GGUF Q6_K has been exercised on **Kaggle Tesla T4 ×2** using a bounded GPU0 prompt-encoding phase and independent GPU0/GPU1 inference workers. Previous end-to-end acceptance includes authenticated browser submission, 1024 × 1024 PNG delivery, SHA256 integrity, and image View/Download. See the technical evidence index for the exact artifacts and their verification scope.

## Launch on Kaggle

1. Select **GPU T4 ×2** and enable Internet access for the initial setup.
2. Attach the Kaggle GGUF model `dangkhoa2016/unsloth-z-image-turbo-gguf`, variant `q6-k`, version 1, and the dataset `dangkhoa2016/z-image-turbo-diffusers-support-components`.
3. Open [the showcase notebook](../notebooks/kaggle-dual-gpu-production-demo.ipynb). Run its cells in order to check the inputs, start API/Studio and the GPU queue consumer, then publish the two HTTPS websites.
4. Use Studio's generated demo login, submit a prompt, and verify the job, artifact and image retrieval. Check both GPUs with separate jobs when demonstrating dual inference.

## Environment compatibility

The repo supplies source and launch orchestration; it deliberately does not distribute model weights, private job artifacts or runtime databases. Rebuilding a runtime requires compatible GPU/PyTorch/Diffusers/Transformers components and the model inputs above. An earlier Kaggle runtime passed the recorded GPU checks; **a new Kaggle session must still be tested on its own before its run can be marked verified**. GitHub's repository audit checks structure and syntax, not actual GPU execution.

## Further reading

[Deployment profile](deployment-profile.md) · [Architecture](architecture.md) · [Kaggle guide](kaggle.md) · Technical evidence
