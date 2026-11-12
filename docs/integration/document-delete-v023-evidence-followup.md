# v0.2.3 文档软删除：QA_BLOCKED 后证据补齐

日期：2026-11-12，Asia/Shanghai。Agent C 状态：**BACKEND_API_PARTIAL，补验证据已就绪，待独立 QA 复核**。

本报告补齐 DEL-E01、DEL-E02、DEL-E03 的开发方复验证据，不修改 QA 已提交的报告，不自行签发 QA_PASS、READY_FOR_RELEASE 或 RELEASED。业务代码未变更；初轮交接误记的 db.py 已更正为 database.py。

## 冻结身份

| 项目 | 核对值 |
|---|---|
| 后端源码 / OCI revision | cd3fd89441cf385cf631f0adc7ba096a9743900e |
| 本轮开始时原开发分支 HEAD | 355b9136a70b58f9db703f6bc2832a61a420296d |
| 候选镜像标签 | market-regulation-workbench:candidate-v023-delete-cd3fd894-f019eeb |
| 候选镜像 ID | sha256:80bedbd207c469ae6d0077b2ef0d0dbe6075bea9f877dc5c2a02f4d1c15c3e89 |
| 候选前端 revision | 019eeb2433d41388737e8c05bab0919ace03538b |
| 运行期契约 | frontend-api-v0.2.3-draft-3；30 路径；文档详情 GET 和 DELETE |
| 正式运行容器 | market-regulation-app-1 |
| 正式镜像标签 | market-regulation-workbench:sha-30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 正式镜像 ID | sha256:e2a94f67ffacef9e780e06bc1484cb5e7dde4b287fa5ef340a666f5e573e52a3 |
| 正式源码 / OCI revision | 30c4663ceb93cbba302b322f1ecee0d06d80bfb4 |
| 8180 实际身份 | 既有 v0.2.2 服务，0.2.2-api-candidate，22 路径，无 DELETE；未切换 |

正式容器完整 ID 为 b23198928dda0e75ff7ad40d3ce8170da825cb81922526a1db65e8b5815621c1；最终复核 healthy，启动时间仍为 2026-11-12T00:54:43.04620371Z。本轮只新增测试、测试辅助文件和文档，不重建候选、不更新标签、不修改正式数据库、授权或 ACTIVE。

## DEL-E01：真实隔离 PostgreSQL / 知识库

新增 tests/test_document_delete_pg.py，显式选择 DocumentDeletePGTests 类。仅当 DELETE_PG_FIXTURE_ISOLATED=1 且明确提供测试连接才执行；初始化要求数据库为 qa_round01、相关业务 Schema/表尚不存在，否则拒绝覆盖。不得指向正式数据库。

使用现有 pgvector/pgvector:pg16 镜像的短期容器，network none、无宿主端口、数据目录 tmpfs、无正式状态挂载。候选容器共享该临时网络命名空间，仅访问本机测试 PG。按既有 round01 SQL 夹具创建 document_review 表，按镜像内 Database.initialize 创建完整 public 知识库表。DDL 和合成插入仅在此全新临时库执行，不是迁移正式结构。

API 引用核查使用专用 SELECT 账号 delete_evidence_reader；管理员连接仅用于准备夹具与前后快照。没有替换引用回调或数据库适配器，实际执行 ReviewReader 和 Database 的 PostgreSQL 查询。

| 用例 | 结果 |
|---|---|
| source_file_id 命中 document_review 文档 | 409 document_referenced |
| document_id 命中文档 hash | 409 document_referenced |
| RETIRED 非 ACTIVE 知识库版本关联 source_hash，ACTIVE 为空 | 409 document_referenced |
| 完整真实库内无引用 | 200 deleted:true |
| PG 不可用 | 503，活动上传与原件不变 |
| 知识库连接不可用 | 503，活动上传与原件不变 |

每次 DELETE 前后逐表比较 public 和 document_review 全部业务行，均不变。正常解析输出不生成、不修改；审核和发布不执行。

先以 unittest 执行六项通过，再在全新临时库补跑 **python -m pytest：6 passed**。两次执行不累加计数。首轮辅助测试错误使用无 PDF 文件头的字节导致上传失败，修正夹具后使用全新容器重跑；早期日志保留，未修改业务校验或降低断言。

最终 pytest 容器：agentc-delete-pg-pytest-check-20261112。PG 服务测试后已停止，未删除容器、日志或历史证据。

## DEL-E02：真实浏览器删除流程

新增 tests/check_document_delete_browser_server.py 与 tests/check_document_delete_browser.cjs。复用已安装的 Playwright 和 Microsoft Edge，未安装浏览器依赖。短期容器仍使用冻结候选及其固化前端 dist，只向本机发布临时 18183 端口；不是新的日常联调入口，结束后已停止。

测试只使用合成 ADMIN、USER 与临时上传，真实 Bearer、真实页面点击和确认框、真实 DELETE 与刷新请求。原件和 SQLite 位于 tmpfs，不挂载正式 PG、runtime、语料或授权账本。

| 场景 | 结果 |
|---|---|
| 真实运行期契约声明 DELETE | 页面删除按钮启用 |
| 受控契约去掉 DELETE 方法 | 删除按钮禁用 |
| 合成普通用户尝试删除 | 真实认证返回 403；刷新后行保留，无成功计数提示 |
| 证据引用冲突 | 409；刷新后行保留，无成功计数提示 |
| 引用存储不可用 | 503；刷新后行保留，无成功计数提示 |
| 另一客户端已先删除，页面旧行再次点击 | 404；不计成功，刷新后按真实列表消失 |
| 有明确授权且无引用 | 200；显示接受 1 个请求，实际 GET 文档列表后行消失 |

所有七项断言通过，保存五个删除场景截图与仅含方法/路径/状态的请求记录。方法缺失负向场景仅拦截契约响应以控制门控条件；409、503 使用服务端合成引用回调，实际走业务错误处理。真实 PG 引用逻辑由 DEL-E01 独立验证，不把浏览器受控夹具说成真实 PG 集成。

最终浏览器服务容器：agentc-delete-browser-evidence-v2-20261112。未改前端源码，没有将 Vue 页面 HTTP 返回等同于浏览器验收。

## DEL-E03：环境盘点、获准安装与 pytest

只读盘点发现项目 .venv 与内置 Python 均无 pytest，其他三个工作区未发现常规 .venv/venv/env 解释器；现有九个 Python/后端候选镜像也无 pytest。历史镜像仅作工具盘点，没有被视作当前 v0.2.3 被测版本。

随后用户明确授权在项目既有 .venv/Scripts/python.exe 安装 pytest；安装成功，Python 3.12.16、pytest **9.2.0**。仅该开发虚拟环境新增 pytest 9.2.0、iniconfig 2.3.1、pluggy 1.7.0、Pygments 2.21.0；未改项目 requirements、正式环境或候选镜像。完整解释器位置和前后包清单位于忽略的本地证据，未写入配置仓库。

将获准安装的 pytest 及其纯 Python 模块复制到忽略的测试工具目录，以只读挂载提供给原候选。关闭第三方插件自动发现和缓存写入，设置业务导入优先于工具目录；业务使用镜像内 qa_core，没有挂载宿主业务源码。首次工具装配遗漏 pytest 自带 py.py，补齐该已有模块后重跑；保留工具错误日志，不计为业务缺陷。

| 最终执行 | 结果 |
|---|---|
| 原 110 项回归，python -m pytest | 110 passed，另有 25 subtests passed |
| 新增真实 PG 引用类，python -m pytest | 6 passed |

原 110 项包括文档删除、RBAC、真实隔离 MySQL 审核、API、任务、网关和发行保护。MySQL 仅使用既有 market_review_test_ 前缀隔离配置。原 110 项与新增 6 项是不同用例，但均为 Agent C 自测，不能替代 QA 原有 52 项独立结论。

最终回归容器：agentc-delete-pytest-regression-v2-20261112；未使用正式 8180 容器运行测试。

## 复核方式与证据

复跑 PG 测试需要全新独立空库、显式测试开关及私密的测试连接；不要对已准备夹具重复初始化或清理现有数据。采用以下选择器，不导入重复测试类：

```text
python -m pytest -p no:cacheprovider -q --import-mode=importlib tests/test_document_delete_pg.py::DocumentDeletePGTests
```

浏览器脚本使用 PLAYWRIGHT_MODULE、DELETE_BROWSER_EXE、DELETE_BROWSER_BASE、DELETE_BROWSER_EVIDENCE 指定已有工具和临时入口；拒绝正式 8180 地址。服务端夹具只在独立短期容器运行，不作为正式应用入口或授权配置范例。

本地忽略证据位于 local/delete-evidence-followup/：

- pg-final.log、pytest-pg-final.log、pg-identity.txt、pytest-pg-identity.txt：真实 PG 复验与冻结镜像身份。
- browser.json、success.png、forbidden.png、conflict.png、unavailable.png、repeated.png、browser-identity.txt：浏览器断言、请求序列、截图及身份。
- pytest-regression-final.log、pytest-regression-identity.txt：110 项实际 pytest 结果。
- python-interpreters.txt、pip-before.json、pip-after.json、pytest-install.log：环境与获准安装记录。
- shared-final.txt：正式共享服务未变记录。
- pg-first.log、pytest-tools-first.log：保留早期测试辅助错误，不作为最终统计。

上述原始证据不提交 Git，QA 可在本机只读核验。提交包含可复跑的测试辅助文件和脱敏说明，不包含连接配置、凭证、DSN 或机器绝对路径。

下一步交 QA 对同一候选身份复核三项证据并独立更新验收报告。未经用户最终部署授权，不切换 8180，不开放正式删除权限，不自行解除 QA_BLOCKED。
