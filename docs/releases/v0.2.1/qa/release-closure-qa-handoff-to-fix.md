# v0.2.1 收尾增量问题交接

日期：2026-11-10。按用户最新确认的“功能安全门禁 + 识别质量分级 + 人工复核”验收，不因单个困难样本 CER 超限否决版本；安全限额仍不可绕过。本交接包含一个已复现 P1，不要求重新开发既有 OCR 或入库能力。

## QRC-001：恢复最终结果缓存绕过当前资源安全限额

| 字段 | 内容 |
| --- | --- |
| 优先级 / 状态 | P1 / FAIL，阻断技术安全验收 |
| 样本 | 合成 ENV-CACHE-01，不使用真实文档 |
| 受测业务源码 | `bf66e10753757c2e1f92383755817dd8c31ab336` |
| Fix 交接 HEAD | `c8e624b066a795161901b55bd472ec730b1889ea`，交接文档提交，业务源码未再变化 |
| 实际候选镜像 | `market-regulation-workbench:candidate-v021-bf66e1075375` |
| 镜像 ID | `sha256:ff555f5d00330c199ae5933b97b6a9fc6fa125d9710109f7fcf2213e5ac5f342` |
| 失败模块 | `qa_core/document_parsing/mineru_service.py`，`MinerUService._local`，恢复 `local_result_path` 分支及其后的 sink 调用 |
| 回归测试 | `tests/test_release_qa_acceptance.py`，`FinalResultCacheSafety.test_current_limits_reject_pre_database_final_cache_in_all_strategies` |
| 性质 | 原有最终缓存恢复路径遗漏安全复验；不能据此认定 bf66 新增了该路径。当前 SAFE-001 修复覆盖 local-candidate 缓存，但未覆盖最终 normalized 缓存 |

### 复现与证据

1. 创建合法 PNG 和本地任务，保存匹配文件摘要的旧成功 `normalized.json`；模拟解析已完成、数据库失败后持久化的 `local_result_path` 检查点。不修改源文件或历史缓存。
2. 当前图片限额设为 50 像素，输入为 10×10，分别以 local、auto、remote 策略恢复；另用未打补丁的默认 20,000,000 像素限额及 4500×4500 图片恢复 auto。
3. `resume` 后 `run`。预期全部 SAFE_REJECT：任务 failed、错误码 `image_pixel_limit`、sink 零次、云端零次，并保留原始源和历史结果。
4. 实际四个子场景均 completed，记录型 sink 被调用一次，云端零次。默认限额场景 20,250,000 > 20,000,000，证明无需缩小默认限额也可复现。

一个测试方法、四个子场景、一个缺陷；不按四个 Bug 统计。记录型 sink 无真实数据库连接，未把违规结果写入业务库。原始输出保留在 QA 忽略目录：

- `local/v021-release-final/image-default-cache-safety.log`：实际候选镜像，四个失败子场景。
- `local/v021-release-final/final-policy-regression/` 及同名 `.log`：绑定实际 Fix 导入路径的独立完整回归。
- `local/v021-release-final/confirmed-regression/`：此前同一路径三个策略的独立复现，不重复计数。

候选镜像最小复现（从 QA 仓库根目录运行；测试只写容器临时目录，不修改业务源码）：

```powershell
$qaCase = (Resolve-Path tests/test_release_qa_acceptance.py).Path
docker run --pull=never --network none --read-only --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges --memory 512m --tmpfs /tmp:rw,nosuid,nodev,size=64m --env PYTHONPATH=/app --mount "type=bind,source=$qaCase,target=/qa/test_release_qa_acceptance.py,readonly" --workdir /app --entrypoint python market-regulation-workbench:candidate-v021-bf66e1075375 -B /qa/test_release_qa_acceptance.py -v
```

镜像内实际导入 `/app/qa_core/...`；仅挂载 QA 测试，未挂载替代业务源码。镜像代码身份另已核验。错误摘要：`AssertionError: 'completed' != 'failed'`，观察日志 `sink_calls=1`、`cloud_client_calls=0`。

### 已确认根因与修复验收

当前分支读取最终缓存仅检查结果 document_id 与文件摘要，不重新执行当前资源限额检查。后续仅检查缓存里的 parsing_status/safety_rejection；旧成功结果自然不携带当前拒绝，直接进入 sink。

建议在最终缓存复用及 sink 之前统一执行当前输入安全检查，维持一致的类型化拒绝；不要为此删除、覆盖或无条件重新解析历史 normalized 结果。继续保护已有成功结果摘要和幂等。

验收要求：四个子场景全部通过；正常缓存恢复不重复 OCR/云端调用，不改变既有结果摘要；local-candidate 安全回归保持通过；新上传的 S00019 仍 SAFE_REJECT；被拒绝结果不得进入 sink。Fix 提交新的完整源码 SHA，QA 重新绑定并独立复测。不要通过修改测试断言、真值或版本闸门绕过。

## 其他收尾项的职责

- 复杂样本识别质量不足：按新标准保留分级、候选和人工复核，不要求为了版本通过使所有样本达到旧 98%/95% 阈值。质量本身仍不得标 PASS。
- 旧 S00010 官方任务：本轮仅 GET 恢复返回 403，BLOCKED；需要核对旧任务访问权限/服务端保留状态，原因尚未证明。禁止盲目重提原文或清空预算账本。
- Windows 整机重启验证：仍未执行，由用户安排。候选容器 restart 已通过，不能替代整机重启。
- 当前活动应用仍为旧镜像；本次仅验证候选，不自动替换服务。不能把候选验收等同部署验收。

QA 交接提交使用包含本文件和回归测试的真实 Git 提交识别；提交后在回复中给出完整 SHA，不自引用尚未生成的 SHA。未 Push，未自动唤醒其他会话。
