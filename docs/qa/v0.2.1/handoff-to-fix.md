# v0.2.1 QA → Fix 正式交接

冻结源码：`5ed1ba6339dc817f53747c0db7cbcbde3224dd3b`。本次只交付下列有证据的问题；原始测试集和labels保持不变。

## Q021-001：结构增强失败丢弃已可读原生正文

- 优先级P1：已有原生正文被完全丢弃；错误状态可见，不声称绕过复核或云端外传。
- 纯合成复现：创建双栏PDF，包含LEFTMARK与RIGHTMARK，预检looks_multicolumn为真、原生表格为空、pdf_page已提取两个标记；Structure runtime固定抛IngestionError。
- 预期：增强失败仍保留可追溯原生候选，且保持人工复核；可以返回候选字段或原生回退，不强制所有多栏直接Native。
- 实际：DocumentParser返回failed页，raw_text为空，raw_result为空字典；两个已提取标记均丢失。
- 定位：document_router.py中native=pdf_page后选择Structure，异常处理仅构造空错误页，未保留native。
- 回归：tests/test_v021_native_preservation.py，1个方法实际FAIL，执行不需要模型、数据库或真实语料。

## C021-001：表格配置操作建议

本地表格模型完整，默认OCR_ENABLE_TABLES未设置所以关闭。真实有框线第4页关闭0表、开启1表30cells，数据与哈希已留证。请给现有入口提供明确显式opt-in的最小操作说明；不擅改全局默认、服务、模型或整个表格模块。

## 原9项差异分类

原严格一致率保持44/53，不重写expected_engine。6个多栏Structure/Native差异由现有复杂版面策略解释，但是否满足标签应保留待审定；2个扫描页Structure/OCR差异由网格增强解释，同样不能自动记标签PASS；1个42,442,380像素图片超过20,000,000限额，属于安全拒绝，不允许放大阈值迎合标签。
Q021-001是独立确定真值的合成异常分支缺陷，不把上述8个策略差异直接变成该Bug，也不把缺标准全文/结构当可用代码“修好”的问题。

## 修复边界和验收

仅复用DocumentParser、既有质量与复核语义，保留错误原因、原生来源、增强失败依据。不得改写MinerU客户端、不可变结果、法律复核、labels或资源阈值；不下载模型、外传、安装依赖、操作数据库或Push。
先跑新最小失败回归与受影响的原生/混合/多栏路由测试；不重跑149或新增重模型测试。Fix返回精确源码SHA及自有修复报告，QA独立定向复测。

## Q021-002：CLI静默覆盖显式表格环境开关

优先级P2。scripts/test_document_parsing.py的--tables使用store_true默认False，随后replace(ParsingConfig.from_env(),enable_tables=args.tables)在未提供flag时把显式环境True重置为False。benchmark.tables也记原始args而非实际配置。纯Mock复现4项中两项缺陷失败、两项默认/显式flag控制通过。修复仅保留from_env语义、显式flag可开启、报告记录effective值；不要求新增--no-tables或修改全局默认。
