# Vue 前端 Docker 部署

前端页面入口为 `http://127.0.0.1:8181`；唯一业务后端仍为 `http://127.0.0.1:8180`。浏览器只请求同源 `/api/*`，前端容器通过既有 Docker 网络转发到 `market-regulation-app-1:8180`，保留认证与后端权限门禁。

Docker Desktop 项目 `market-regulation` 新增 `frontend` 服务。Compose 文件仅管理前端，不声明或重建 app、db、mysql、redis。不要使用 `--remove-orphans`、`down`、`prune` 或删除卷来消除其他服务提示。

## 构建和启动

使用已有前端 node_modules；不自动安装依赖。前端工作树必须已提交且干净。构建仅写入本工作树 ignored local 目录，不覆盖前端 dist，不自动启动容器：

```powershell
./scripts/frontend-docker.ps1 -Action Build -FrontendRoot '<前端工作树>/frontend' -Image 'market-regulation-frontend:<唯一版本标签>'
./scripts/frontend-docker.ps1 -Action Start -Image 'market-regulation-frontend:<唯一版本标签>' -Port 8181
./scripts/frontend-docker.ps1 -Action Status
```

若前端有并行未提交改动，保留原文件，由负责人提交后构建；或使用 `git archive <完整SHA> frontend` 导出的独立快照构建，不能将混合内容标为该 SHA。镜像历史标签不覆盖。

首次 Nginx 镜像拉取因 Docker Hub 连接超时失败，因此采用本机已验证运行环境作为静态服务基础层。它只启动 `deploy/frontend/server.py`，不启动 OCR、模型、任务 worker 或数据库服务，不挂载状态目录及凭据。镜像体积复用原运行层，后续可独立优化为轻量镜像；不影响当前前端功能。

基础镜像默认现有 `candidate-v022-4fc4cf124a12`；构建前需核对其完整镜像 ID，禁止把标签作为不可变证据。支持 `-BaseImage` 指定其他已验证本地标签或仓库 digest 引用。Dockerfile 的构建上下文只需要 `dist/`、`server.py`；不能把源码树、环境文件或访问码放入镜像上下文。

## 安全和验收

- 仅绑定本机 8181，容器非 root、只读根目录、无数据卷、无额外 capabilities。
- API 代理固定上游，不接受浏览器传入的目标地址，不自动重试写请求，不打印访问查询参数。
- Vue History 路由刷新返回入口页面；缺失静态资源返回 404；页面不缓存，内容哈希资源长期缓存。
- `/healthz` 仅证明前端服务运行，不宣称模型或数据库在线。
- 自动测试：`python -m unittest tests.test_frontend_gateway -v`，使用合成页面和模拟上游验证认证头、Range、查询参数、上传正文及错误状态透传。
- 发布后核对容器 health、页面和资源、API 401 透传及前后端镜像身份。该检查不等于登录后的七页面业务 QA PASS。

## 回滚

已有前端镜像保留；回滚时仅对 frontend 使用之前核实过的镜像执行 Start。首次部署若需撤销，只停止新前端容器即可，8180 及原有数据服务继续工作。后端切换仍遵循独立批准和 QA 冻结规则。

部署实测和不可变身份记录见 `docs/integration/frontend-docker-handoff.md`。
