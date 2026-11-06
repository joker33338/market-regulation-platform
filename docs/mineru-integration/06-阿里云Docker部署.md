# 部署状态及当前运行方式

用户本轮最新指示：先直接调用官网 API，不部署服务器。因此 GAP-006 的 ECS 部署暂缓，
未启动云服务器、SSH、GPU 容器或下载 MinerU 模型，也没有把本机 CPU Compose 当作 GPU 部署。

当前可用版本在本机运行：

```text
./scripts/start_parsing_app.ps1 -Port 8180
```

仅监听 loopback，单 ASGI 进程；打开 http://127.0.0.1:8180。
工作台访问码单独保存在忽略的本地文件，官网 Key 和 PG 配置保存在忽略的运行配置。
访问码属于应用鉴权，与官网 Key 不同。页面不会获取官网 Key。
启动脚本遇到端口占用会退出，不停止已有服务。

已固定并在独立 API 环境验证 requirements-api.txt；原 OCR/BGE 环境未升级。
原 Docker COPY 缺失通过提供合成示例修复；尚未执行实际 Docker 镜像构建。

未来恢复 ECS 部署时，以 [官方 Docker 方案](https://opendatalab.github.io/MinerU/zh/quick_start/docker_deployment/)
为依据，固定 4.1.7 候选包版本、基础镜像 digest 与完整依赖，并核对实际 OpenAPI。
自部署接口与官网 v4 保持独立 Provider，不以官网调用成功宣称自部署验收通过。
