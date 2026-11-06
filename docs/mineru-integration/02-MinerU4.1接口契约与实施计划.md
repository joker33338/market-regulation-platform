# 两种协议及实施边界

2026-11-06 核对官方资料。用户随后明确先直接调用官网、不部署服务器。

| Provider | 契约 | 结果结构 | 本轮验证 |
| --- | --- | --- | --- |
| self_hosted | 4.1 Tasks：JSON POST /v1/tasks，回执 PUT、GET、POST cancel | 默认 ZIP 三个标准文件和图片 | 合成 Mock 验收；候选服务补丁 4.1.7，未部署 |
| official | 官网精准解析 v4：POST /v4/file-urls/batch，PUT，GET /v4/extract-results/batch/{batch_id} | full.md、content_list、layout 等 | 真实合成 PDF 与生产 Adapter 恢复验证通过 |

官网配置使用 `MINERU_PROVIDER=official`、`MINERU_MODE=remote`、
`MINERU_API_URL=https://mineru.net/api`、`MINERU_CLOUD_MODEL=vlm`。
官网 model_version=vlm 不等于自部署 Standard 档位，也不证明服务运行 4.1.7。
实际返回版本和模型分别保存在来源元数据，不伪造未知版本。

客户端只向 API 同源添加 Key；上传和下载仅接受已配置或官方文档指定的 HTTPS 来源。
创建请求不自动重试，返回状态先持久化。官网 data_id 是客户端关联标识，不冒充自部署服务分配的 file_id。
官网文档没有取消接口，因此官网取消仅停止本地处理，响应显式标记 local_only。

参考：[Tasks](https://opendatalab.github.io/MinerU/zh/usage/tasks/)、
[4.1 迁移](https://opendatalab.github.io/MinerU/zh/reference/migration_4_1/)、
[官网 API](https://mineru.net/apiManage/docs)、
[4.x 输出](https://opendatalab.github.io/MinerU/zh/reference/output_files/)。

已阅读用户提供的 [langchain_mineru](https://github.com/opendatalab/MinerU-Ecosystem/tree/main/langchain_mineru)：
precision 使用 Token，默认 flash 不使用 Token，Loader 主要返回 Markdown。
本项目需要持久化状态、原始 ZIP 和结构化结果，故参考其接入约定但不替换现有 RAG，未安装 LangChain 或本地 MinerU 模型。
兼容其凭据名称 MINERU_TOKEN；不与 MINERU_API_KEY 同时填写不同值。
