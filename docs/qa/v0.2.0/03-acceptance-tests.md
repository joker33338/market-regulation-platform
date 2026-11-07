# v0.2.0 可执行验收测试说明

## 已执行状态

对 Fix `d2a4c673c596945be14fa4d91a995fd8086e2b31` 运行 `tests/run_v02_acceptance.py`：15 个方法，5 PASS、10 SKIP、0 FAIL。五项 PASS 证明现有原生/OCR/Structure/质量/复核能力可复用；十项 SKIP 是尚未实现的双引擎策略，不能算功能完成。

```text
python -B tests/run_v02_acceptance.py --source <isolated-fix-checkout>
```

使用当前已有解释器/API依赖和可写临时目录，不下载模型。默认没有测试适配器绑定；每个 A–J 方法都会明确 SKIP。绑定生产实现后，同一命令逐项执行新验收。该测试进程上限 60 秒。

## 适配器是测试协议，不是生产 API

`MARKET_REGULATION_DUAL_ENGINE_TEST_ADAPTER=tests.<已审查模块>:<函数>` 由 Fix 提供候选测试适配器，QA 审查后绑定。函数接受场景字典与合成文件 Path，调用真实双引擎业务入口，以可观察信息返回字典。

适配器只能创建输入、注入假 OCR/HTTP、采集实际调用与结果；禁止按 case_id 返回预设期望值，禁止在测试替身中实现路由策略。本文字段不代表现有 HTTP 或数据库字段，也不强迫 Fix 新增同名生产字段。实际路由/配置/存储设计必须另行说明如何映射。

测试文件为 `tests/test_v02_dual_engine.py`：ExistingCapabilities 的五个复用测试已通过；DualEngineAcceptance 的十个方法对应 A–J。未绑定时跳过，不设 xfail 来掩盖失败。绑定后真实 HTTPTransport/AsyncHTTPTransport 与 urllib 网络调用被测试拦截，Mock/ASGI 可用。

## 场景输入与观察

公共场景提供 case_id、cloud_mode=mock、默认 authorized_cloud=False、sensitive=False、max_cloud_calls=8、review_approved=False。低质量、异常、复杂布局、故障和重复操作是可控测试输入，不是伪造的 MinerU 服务字段。

所有场景都校验源文件 SHA-256 前后相同，返回 source_sha256 必须对应真实合成文件。按场景采集：

| 测试 | 必要观察/断言 |
| --- | --- |
| A | engines 包含 native；cloud_submissions=0，Word/PDF 都执行 |
| B | engines 包含 paddle_ocr；cloud_submissions=0 |
| C | complex_layout_detected、layout_preserved 为真；有 route_reason；允许原生可信表格、本地 pp_structure 或获准 mineru_official |
| D | warnings 非空、local_result_preserved；未授权零提交，授权候选一次提交 |
| E | review_required、original_text_preserved、warnings；分别覆盖条号/金额/日期 |
| F | cloud_calls≤8、cloud_submissions≤1；有 failure_reason，保留本地结果 |
| G | 默认/敏感两种情况下，未授权均零云端提交 |
| H | 同时保留本地与官方引擎；provenance 包含原因、质量、raw_results、page_numbers、source_file_id、parser_versions；缺版本必须说明原因 |
| I | database_backend=isolated_postgres；重复前后行数相同；失败不覆盖 prior_record |
| J | ingestions_before_review=0；复核后 hits_after_review>0；来源关联仍存在 |

I 必须接真正的 QA 专用 PostgreSQL；不允许把内存列表/SQLite 伪装成 isolated_postgres。J 使用合成、可复核的法条数据，沿用现有 pipeline，不绕过 Mock/表格/人工审核保护。

## 回归命令与边界

同时执行第一轮现有验收：

```text
python -B tests/run_round01_validation.py --source <isolated-fix-checkout> --include-source-tests --result-json <ignored-result>
python -B tests/round01_isolated_postgres.py --source <isolated-fix-checkout> --output <qa-local-output>
```

数据库助手只使用已存在镜像，新建内部网络和专用数据库，保留数据而不清理业务库。当前本地 PASS 不等于真实官方识别、部署或费用验收。
