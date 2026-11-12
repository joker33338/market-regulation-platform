# 新前端 Docker 部署交接

核验日期：2026-11-11（北京时间）。已部署到现有 Docker Desktop 项目 `market-regulation`。

## 访问方式

- Vue 新前端：`http://127.0.0.1:8181`。
- 唯一业务后端：`http://127.0.0.1:8180`。
- 浏览器请求同源 `/api/*`，由前端服务转发至既有后端；不内置 Token、不使用 DEMO 冒充正式数据。

## 不可变版本身份

| 项目 | 完整值 |
|---|---|
| 前端源码 SHA / OCI revision | `b511f388def788fa1b07fdfeab9a93c7342f4cd3` |
| 前端镜像标签 | `market-regulation-frontend:v022-b511f388def7-frozen` |
| 前端镜像 ID | `sha256:fac113a21f0fad9cd25c3ede3831f62c15130e42d18180c18d4ff26b7c3bed16` |
| 前端容器 | `market-regulation-frontend-1` |
| 前端容器完整 ID | `dc431b0d8c02fc541c6d3f2716712a97bd43fbf66250267fa9af44f27d858a36` |
| 前端实际端口 | `127.0.0.1:8181 -> 8080/tcp` |
| 后端镜像 OCI revision | `4fc4cf124a120762593064676ea5f8dbe2394119` |
| 后端镜像标签 | `market-regulation-workbench:candidate-v022-4fc4cf124a12` |
| 后端镜像 ID / 前端复用基础镜像 ID | `sha256:8f169cd82cc1bf55807eb48a9f75e0b5206ac4cb10ca27c38fe206a85e93d7a4` |
| 后端容器完整 ID | `de1c0271a55eb579ef43073ad3f7109732bd409bb49259087451b6f32fe401af` |
| 后端容器名称与映射 | `market-regulation-app-1`，`127.0.0.1:8180 -> 8180/tcp` |
| 部署前后后端启动时间 | `2026-11-11T05:49:06.552578421Z`，一致 |
| 部署前后本工作树 HEAD | `1f9abf845eeea19cafdf23a46a9fb1e64b81dca2`，不是 8180 运行源码 |

本表运行身份来源为 Docker inspect 和端口响应。后端源码为镜像标注 revision，本轮未逐文件重新比对后端源码。前端代理部署代码由本交接的 Git 提交记录，不混入前端 OCI revision 所表示的 Vue 业务源码。

## 构建和范围

Nginx 拉取因 Docker Hub 连接超时失败。最终前端镜像复用本机现有运行依赖，单独运行静态页面及固定上游代理，不加载业务服务或模型，没有后端状态/凭据挂载，没有新增业务后端实例。

发现前端工作树有并行修改后，最终通过 `git archive` 导出上述完整前端 SHA 独立构建，复用已有 node_modules。未修改、暂存或覆盖前端负责人的未提交文件。历史首次构建镜像保留，但最终只运行本表 frozen 镜像。

已完成：类型检查、Vite 生产构建、网关合成测试 2 项通过、一次性无网络容器静态检查通过。最终运行镜像的七页面路由及 healthz 均返回 200，29 个 JS/CSS 资源均返回 200；8180 和 8181 的匿名 `/api/parse/info` 均返回 401。frontend healthy；后端容器 ID、镜像 ID、启动时间未变化。

网关测试覆盖 Vue 路由回退、资源 404、认证头、Range、查询参数、上传正文和响应状态透传，不调用真实 OCR 或写入共享数据库。未执行登录后的七页面浏览器端全流程，不能签发业务 QA PASS。构建存在大资源块提示，未阻断构建。

## 维护与回滚

部署文件：`compose.frontend.yaml`、`deploy/frontend/Dockerfile`、`deploy/frontend/server.py`；操作脚本 `scripts/frontend-docker.ps1`。详细操作见 `deploy/frontend/README.md`。

后续前端更新独立提交、构建唯一镜像并验收，再只替换 frontend。后端 8180 更新仍须按统一镜像规则批准。首次部署撤销可仅停止 frontend；不停止 app，不删除任何容器卷或历史镜像。Compose 发现同项目其他服务时不得使用 remove-orphans。
