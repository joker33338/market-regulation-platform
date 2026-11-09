# v0.2.1 服务启动、重启与数据库补覆盖

日期：2026-11-09。本报告根据既有证据重新整理，只修复此前中文编码损坏，不重跑测试或改写原始证据。

## 身份与实际命令

- 源码：`ee7dd7e6c8243e98c9f1bf995a4c57c555611786`。
- Fix 传输：`e16b4e241651a0641bdccac8420a64290e40869f`。
- 镜像：`sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1`。

```text
python -B -m uvicorn qa_core.document_parsing.mineru_api:create_app --factory --host 0.0.0.0 --port 8180 --workers 1 --log-level info --no-access-log
```

源码只读挂载、非 root、只读根目录、cap-drop=ALL、no-new-privileges、临时/tmp、内部独立网络，仅合成运行目录可写。MINERU 为 mock、双引擎关闭、数据库 DSN 为空，没有模型或语料挂载、真实云请求。Token 仅在忽略配置中。

没有独立 `/health`；用 `GET /` 与认证 `GET /api/parse/info` 检查现有页面和就绪状态。已提交 Dockerfile 的 CMD 是 sleep infinity，原 Compose 应用没有发布 API 端口，不能用其运行状态替代本次真实服务。原应用和用户未提交文件未修改。

## 实测结果

| 检查 | 结果 |
| --- | --- |
| PID1 factory 监听 0.0.0.0:8180 | PASS |
| 容器内部真实 TCP 根页面、认证 info | PASS，200 |
| 无认证 info | PASS，401 |
| 合成上传、Mock 解析、完成轮询、结果读取 | PASS |
| 重复幂等键 | PASS，同一任务 |
| Docker restart 后同 CMD 自动运行 | PASS |
| 重启后任务、结果、幂等状态保持 | PASS |
| 日志 ERROR 或 Traceback | 未发现 |
| Windows 127.0.0.1:8180 | BLOCKED，实际发布映射为空 |

docker exec 仅运行客户端，没有用于启动第二个 Uvicorn。QA 容器及 runtime 保留，restart policy 为 unless-stopped。旧中间源码容器确认无活跃任务后正常停止；原应用服务未操作。端口根因见独立网络报告，内部成功不能当作宿主可访问。

## 完整回归与五项 PG

最终源码发现191唯一方法：断网容器184 PASS、0 FAIL、7 SKIP；Windows专项仅补一项通过后为185 PASS、6 PG缺口，没有虚增第192项。

后经明确授权，只补执行 ParsingPostgresTests 两项、Round01PostgresAcceptance 两项和 DE-I 一项，五项全部PASS、无失败或跳过。预检 qa_round01、qa-postgres、test-only 标记、内部网络/无主机端口及现有 document_review 五层主键/故障约束。额外游标守卫拒绝 DELETE、TRUNCATE、DROP、CREATE、ALTER、COPY、GRANT、REVOKE，原业务和断言未改。

成功新增五条合成 documents，失败事务回滚；全部历史 parse_id/report_sha256 保持，专用库恢复停止，未操作用户 market_regulation 库。去重后为 **191唯一方法，190 PASS、0 FAIL、1 BLOCKED**。

唯一剩余方法：`tests.test_postgres_integration.PostgreSQLIntegration.test_isolated_schema_build_publish_query_rollback`。原方法含 CREATE、initialize、DROP；publish 自身还有 law_chunks/mr_active_chunk_map 的投影 DELETE，不能把抑制 DROP 描述为完全无删除。

最小待审批路径：在专用库新建随机空 schema，表/索引限定新 schema；public.vector 必须已存在，不安装扩展。允许仅本次新 schema 合成投影表的业务 DELETE/更新，保留原断言，抑制最后 DROP 并保留数据；不污染历史 schema。此第六项未执行，不签版本 PASS。

## 证据摘要

原日志、容器标识与私有配置仅在忽略目录。

| 证据 | 原始字节 SHA256 |
| --- | --- |
| 完整基线 summary | `c875cf2849bb2fdae3c64e28b2c04c3251ec84611bc882ebcd143d8abcaa7a10` |
| Windows 补覆盖后 coverage | `c6e6f5a249f67c8c33bb05d5567b2c6a7d9fe119d2484371485254705969b8fc` |
| restart.json | `c2206b5f4efa2a1b056e4d267f4bcefa6ce956e2a638d60a1fc8e128400c4ef2` |
| 五项 PG result.json | `1d68d100fb22fde16b584204803ba84ea71e342a52df6baae80378feb0a3aea0` |

最终逐方法合并见本地 coverage-after-pg-five.json。本报告不代替主 QA 的真实云批次、质量裁决或最终 gate。
