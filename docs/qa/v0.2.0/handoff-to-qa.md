# v0.2.0 交回 Agent A：待独立回归

- 开发/交接分支：`feat/ocr-dual-engine-v0.2`。
- 角色：Fix；复用原 Fix 工作树，保留 `fix/round1` 既有历史，无历史重写。
- 完整受测代码 SHA：`8badb995592771ff099cf52570621ba29ad37533`。
- 双引擎主实现：`943f942c55aad331a97bf8e6ce32c96c3692c73d`；边界测试：`a5065d7b4fcf68caeb54c376f1eea7bf1db5a4eb`。
- 本文件所在的最终交接提交只增加报告，完整 SHA 由会话/Git 提供；QA 应在自身独立工作树检出该 SHA 后复测。
- 接收的 QA READY：`a0c20a9e698d53ce06cd97dceaa1aa188dd042f3`；v0.1 PASS：`75c9c1c5e1c263ddc563e8d73ac09ab091789986`。

DUAL-001 至 DUAL-005 已实现，随后完成 requirements 统一。配置、修改文件/函数及实际证据详见同目录 `04-implementation-report.md` 和 `docs/mineru-integration/v0.2.0.md`。不存在已知新增回归失败；这不是 QA 对本版的 PASS 声明。

## 复测命令

复用现有环境，不需要新建虚拟环境或重装模型。先绑定真实业务测试适配器：

```powershell
$env:MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER='tests.dual_engine_adapter:run_scenario'
python -B tests/run_v02_acceptance.py --source .
python -B -m unittest tests.test_dual_engine_policy -v
./scripts/run_fix_regressions.ps1 -DualEngine -Python <existing-python> -ApiPackages <existing-api-site-packages>
python -B tests/round01_isolated_postgres.py --source . --output local/v02-qa-postgres --include-v02
```

`-Python` / `-ApiPackages` 用 QA 已有环境路径替换；不要把实际路径或连接信息提交到报告。数据库工具要求干净检出、已有本地镜像，仅创建专用内部数据库；不使用业务库、生产库或默认 Compose。没有独立数据库时 I 会明确跳过，不能算验收通过。

## Fix 实测结果

- 专用 PostgreSQL 阶段：20/20 PASS，包含 A–J，源 `943f942`。
- 完成全部代码及依赖清单变更后执行一次完整回归：149 项中 143 PASS、6 条件跳过、0 失败，源 `8badb99`。
- 6 个跳过的数据库方法均在专用 PostgreSQL 阶段实际 PASS；两阶段按方法 ID 去重，149 个用例均有通过证据。两个阶段的 SHA/范围明确分开，不宣称单次全量无跳过。
- 已有环境的 43 条唯一依赖约束匹配；页面/启动脚本语法和 Git 空白检查通过。没有安装/升级依赖。

## Agent A 重点验证

1. 在最终交接 SHA 上重新绑定 A–J，尤其专用 PostgreSQL I；复核后 RAG J 使用演示向量，仅验证原流程兼容。
2. 原生/简单扫描不无故外传；服务器缺许可、过期、敏感标记、混合批次和撤销许可时拒绝上传；请求参数不能授予外传权限。
3. 超时、429、500、请求/文件/页预算；不确定 POST 不重提；中断继续绑定原远端任务。
4. 双端原结果/哈希/页码/实际可得版本可追踪；数据库提交后断连重试不重复、不覆盖旧记录。
5. 新旧 API 和上传页展示；启用 `DUAL_OCR_ENABLED=1` 后旧客户端默认本地。云端开关仍默认关闭，真实原语料不用于测试。
6. 统一 requirements 的新安装与 Docker 构建尚未执行，请作为独立环境验收项，不能据现有环境回归推断构建已通过。

已冻结失败快照需新任务重新解析；DOCX 云端物理页数、真实模型/云端批量质量、GPU 与生产部署边界见实现报告。没有已确认未处理的 P0/P1，但这些未验证事项不被包装为通过。

本次通过本地 Git 分支及本文正式交接。协调器保持只读，未自动分发或发送消息；未 Push、合并主分支、修改生产数据库或部署生产服务。
