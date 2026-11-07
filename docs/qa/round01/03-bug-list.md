# 第一轮 Bug 清单与最终复测状态

更新：2026-11-07。最终受测 Fix：`d2a4c673c596945be14fa4d91a995fd8086e2b31`；修复代码：`0cfb4f2f12d5fd87a57c0a2cacdc92a4cf54d2a4`。共 5 个已确认 Bug，当前全部 PASS，无新确认的未解决 P0/P1。以下初始失败来自实际运行；原始英文历史保留在 Git 旧提交中。

## DOC-001 / R01-001，P2：空文本误报成功

- 样例：合成 E001/E002，分别为空文件和纯空白；不使用语料正文。
- 模块：document_router.py::DocumentParser.parse，TXT/MD 分支及页面状态聚合。
- 首次失败源：`f2a5c925f0305a2e7df21f750b20bed63db40de3`。
- 复现测试：test_round01_regressions 的两个 test_R01_001 方法。
- 预期：没有有效文本不能标记成功。旧实际：success；日志摘要：'success' == 'success' 导致断言失败。
- 根因：原生文本页使用默认成功状态，没有有效文本检查。
- 修复方向及已实现行为：标记 needs_review，并保留合法空白 PDF 行为。
- 验收：两个原断言及旧解析回归全部 PASS。

## OCR-001 / R01-002，P2：中文路径下网格检测失败

- 样例：合成 G001 网格图，使用中文目录；同一像素经解码的正向对照通过。
- 模块：document_router.py::has_grid 及 auto 路由调用点。
- 首次失败源：同上 f2a5c92。
- 复现测试：test_R01_002_grid_detection_supports_unicode_path。
- 预期：相同图像与路径语言无关。旧实际：cv2.imread 返回 None，has_grid 返回 False；断言 False is not true。
- 根因：当前 Windows/OpenCV 环境的文件名读取不支持该 Unicode 路径，静默失去表格提示。
- 修复：Path.read_bytes 加 cv2.imdecode。
- 验收：中文路径、正向对照和原路由测试全部 PASS；不据此声称真实表格质量已经全部验收。

## DOC-002 / R01-003，P1：Docker COPY 资源缺失

- 样例：构建上下文预检 B001。
- 模块：Dockerfile 的 COPY scenarios；相关 smoke_local_model.py 示例资源引用。
- 首次失败源：同上 f2a5c92。
- 复现测试：test_DOC_002_docker_copy_sources_exist。
- 预期：隔离检出包含 COPY 输入。旧实际：scenarios 目录不存在；缺失列表断言失败。
- 根因：迁移后构建文件仍引用未跟踪的资源目录。
- 修复：加入安全合成示例，不用真实资料补位。
- 验收：构建上下文预检 PASS。该 Bug 关闭限于资源缺失；实际新镜像构建 NOT_TESTED。

## SEC-001 / R01-004，P2：ZIP 大小写变体覆盖原始产物

- 样例：合成 Z001，包含 ARTIFACT.BIN 的 ZIP。
- 首次失败源：`f7c4d75e1ff11e2d06d75f44336bf4b89f96aa57`；旧本地 4e5f4a7 也复现。
- 模块：mineru_artifacts.py::unpack/store_artifacts，结果下载 artifact 路由。
- 复现测试：test_R01_004_case_variant_archive_cannot_replace_original_artifact。
- 预期：拒绝保留文件名变体，或始终保留原始下载 ZIP 字节。旧实际：artifact.bin 变成压缩包成员内容，字节一致性断言失败。
- 已确认根因：保留名称检查区分大小写，而 Windows 文件系统不区分；保存原始包后，成员再次写入同一路径。
- 修复：规范化名称后拒绝保留根路径及变体；使用独占临时文件，避免成员与临时文件名碰撞。
- 验收：原 QA 断言、大小写/路径变体、旧文件保护和临时文件冲突测试全部 PASS，普通产物原始字节一致。

## DOC-003 / R01-005，P1：本地损坏文件阻断批次

- 样例：合成 L001 损坏 PDF 与 L002 有效原生 PDF，两种输入顺序。
- 首次失败源：同上 f7c4d75；旧本地 4e5f4a7 也复现。
- 模块：mineru_service.py::MinerUService._local/run/resume。
- 复现测试：test_R01_005_local_batch_bad_pdf_does_not_block_valid_sibling。
- 预期：坏文件记录错误，好文件完成，任务 partial。旧实际：坏文件在前时好文件停留 created；好文件在前时任务误报 failed。
- 根因：仅有任务级异常边界，缺少逐文件隔离和进度持久化。
- 修复：逐文件保存成功/失败，复用写库前的精确结果，恢复时跳过已成功文件，按最终结果聚合状态。
- 验收：两种顺序、错误可见性、精确结果 DB 重试、中断恢复和源内容变化隔离全部 PASS。

## 可运行复现与完整回归

```text
python -B tests/run_round01_validation.py --source <isolated-checkout> --include-source-tests --result-json <ignored-result>
python -B tests/round01_isolated_postgres.py --source <isolated-checkout> --output <qa-local-output>
```

测试由 QA 分支的提交 `4042a23c966c20f94eef17f3c3fc10d7d5f7702a` 提供，选定源码必须是精确 Fix 提交。当前唯一用例 120 PASS。新功能不作为原有 Bug：双引擎策略交给 v0.2.0；部署及泛文档范围仍按 05-missing-features.md 单独记录。
