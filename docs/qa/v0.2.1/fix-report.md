# v0.2.1 两项最小修复记录

## 提交与交接

- 原源码基线：`5ed1ba6339dc817f53747c0db7cbcbde3224dd3b`。
- 已读取 QA 正式交接：`bc0219e9e723f91f38c3f04c3b513a6ee45b6437`。
- QA 红测提交：`4022606420695a22579a82b3ce8e4c03448ca4ac`，四项为两失败、两通过控制。
- 本轮受测代码提交：`6216ae5f40727871b369dfc8c54868ac748c4648`。
- 本报告及结构化交接的传输 SHA 由 Git 在提交后提供，不自引用。

## Q021-001：增强失败丢弃原生正文（P1）

根因：纯合成双栏 PDF 已先完成原生提取，再进入 Structure 增强；异常分支只追加空失败页。
修复限定为本页确有非空 Native 候选的路径，保留原生正文、版面块、表格、PDF 坐标和原始结果。
返回页明确为 `native_pdf` / `needs_review`，保存增强尝试方法、异常类型和安全错误信息，附中文复核警告。
质量评估新增 `layout_enhancement_failed` 复核及回退原因，不把保留正文默认为干净成功。

没有改变多栏默认增强策略。扫描、强制 OCR/Structure、无可用原生候选仍按既有失败行为处理。
候选在每页重置，不能把上一页文字带到下一页。成功的 Structure 结果不走兜底。
未改客户端、外传授权、结果不可变语义或法律人工复核。

## Q021-002：CLI 默认值覆盖显式表格配置（P2）

根因：`--tables` 未指定时为 False，脚本以该值覆盖 `ParsingConfig.from_env()` 的显式启用。
修复为未指定选项时继承进程配置，显式 `--tables` 才启用；基准报告的 `tables` 取实际生效配置。
未设置环境且无选项时仍关闭，不增加新选项，不改全局默认、服务环境或资源限制。

## 真实执行的定向测试

| 执行 | 数量 | 通过 | 失败/跳过 |
| --- | ---: | ---: | ---: |
| Windows：QA 两缺陷用例、配置控制和新增隔离控制 | 7 | 7 | 0/0 |
| 已有镜像：上述7项及受影响解析、历史回归、任务实现和双引擎策略 | 71 | 71 | 0/0 |

第二行已包含第一行的方法，不能相加声称78个唯一方法。
容器断网、非root、只读源码、禁额外权限；只复用既有依赖，没有安装、下载、真实模型或数据库操作。
测试在代码提交前同一修复树执行，随后仅提交对应三份实现和三份回归文件。

```text
python -B -m unittest tests.test_v021_native_preservation tests.test_v021_table_cli tests.test_v021_fix_edges -v
python -B -m unittest tests.test_v021_native_preservation tests.test_v021_table_cli tests.test_v021_fix_edges tests.test_document_parsing tests.test_round01_regressions tests.test_mineru_implementation tests.test_dual_engine_policy -v
```

## 仍保留的质量边界

本次没有修改原始标注、九处标签差异、图像像素限制或默认表格开关。
真实 CER 与人工结构真值不足仍是质量证据限制；本次修复不宣称已解决全部专项质量问题或批准合并 main。
后续 QA 只需对精确代码 SHA 复验失败用例与受影响测试；无须因这两项改动重跑149项、模型或数据库。
