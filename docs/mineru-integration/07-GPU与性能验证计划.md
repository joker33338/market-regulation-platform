# 延后执行的 GPU 验证

用户已要求本轮不部署服务器。本轮没有 GPU 指标，未验证 A10 24GB 并发容量。

恢复自部署时依次核对系统、nvidia-smi、驱动、Container Toolkit、容器 GPU 可见性、
模型完整性、服务 health/tiers、单页与多页合成推理，再测真实获准样本。
先从并发 1 开始记录排队时间、解析时间、吞吐、峰值显存、峰值内存、失败率和恢复情况。
大文件、表格、多栏及混合文档分别评估，不能从简单样本外推全部任务。

官方当前 NVIDIA Docker 使用 vLLM 0.21.0 / CUDA 13.0，并提供 cu129 选择；
NVIDIA CUDA 兼容资料说明 13.x 需要至少 580 系列驱动，具体功能仍需对应 Release Notes 和实机验证。
不在本轮安装或升级驱动、CUDA 或模型。

参考：[Docker](https://opendatalab.github.io/MinerU/zh/quick_start/docker_deployment/)、
[NVIDIA compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)。
