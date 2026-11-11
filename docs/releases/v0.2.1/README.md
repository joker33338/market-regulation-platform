# v0.2.1 正式验收索引

业务基线：`c91547d393ca6b049e216c0051e25271d06d7359`。QA：`843c64d9589091d49bdf68f8576647593bedfaa0`。

- [最终 PASS 裁决](qa/final-release-decision.md)
- [验收边界](qa/final-acceptance-scope.md)
- [机器门禁快照](qa/version-gate.json)
- [当前操作手册](../../current/v0.2.1-guide.md)

qa/ 是从上述提交逐字导出的文档快照，未复制 QA 测试实现。历史 FAIL/BLOCKED 文件保持原文，最新放行依据是 final-release-decision.md。四项镜像测试 ERROR 的环境不适用、Windows symlink SKIP 和旧任务403均未涂改为通过。

## Fix 交付快照

fix/中四份交接／审计文档逐字来自3129479ef763f2d35758a68f514b7053aacdaec4，不代表新业务源码。

- [真实auto补证](fix/auto-reset-fix-verification.md)
- [候选交接](fix/candidate-c915-handoff-to-qa.md)
- [Schema修复交接](fix/schema-and-security-fix-handoff.md)
- [Schema只读审计](fix/postgresql-schema-audit.md)
