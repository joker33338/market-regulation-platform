# 独立持久 localhost 入口验收：nft1

日期：2026-11-09。此报告复用中断前已完成的真实结果，不重跑191方法、真实模型或官网请求。用户批准的新独立镜像与Compose项目，不替换原market-regulation服务，也不使用Windows临时中继。

## 身份

- 业务快照：`67709c4989781594dd6c4723666fdb2c21caaa7b`。
- 初始部署配置：`111f74d98157e386783f74c4242ca06b9df981db`。
- launcher补丁：`a6f3ef49c9dbad815f233307629c67a904855790`、`f4a0af8673066a54b3f3f229b4389ccc734e34a4`。后者为重启/重建验收记录配置；业务镜像未因此改变。
- 实际镜像：`sha256:659fde72ae49637504598da25fac118340f9eddeb4bed2bf9538a5ed0ee94996`，标签nft1。
- 独立Compose项目：`market-regulation-qa-localhost`。入口实际发布 `127.0.0.1:8180→8180/tcp`，backend应用仅internal网络。

应用仍是真实create_app factory、MINERU mock、双引擎与云禁用，测试Token仅从忽略runtime配置内存读取。入口镜像和应用均由可信init先安装规则，再降权运行；无Docker socket或语料/模型挂载。

## 独立实际结果

| 范围 | 结果 |
| --- | --- |
| Windows宿主HTTP根页面、未认证401/认证info200 | PASS |
| 合成上传201、Mock任务202、解析完成、读取结果 | PASS |
| 同幂等键返回相同任务 | PASS |
| B 固定入口peer到应用backend8180 | PASS，200 |
| C Windows到持久Docker发布端口 | PASS，不依赖临时中继 |
| OpenAPI | NOT_EXPOSED，原接口关闭，404 |
| Docker restart app与ingress后服务、任务、结果保持 | PASS |
| force-recreate app与ingress后任务、结果、幂等保持 | PASS，容器ID实际变化 |
| 重启/重建后内核规则重新安装 | PASS |
| A 应用内部127.0.0.1:8180自检查 | PENDING，不能用B/C代替 |
| Windows整机重启后自动恢复 | NOT_TESTED，须用户执行 |

初次预检因launcher尚未提交的变化停在执行前；Fix提交编码/过滤补丁后继续。另一次重启前空闲查询使用了错误的SQLite路径，QA脚本安全停止，没有因此判业务失败；核对实际路径后只补执行未完成的restart/recreate。没有重复完整回归。

## 内核与降权证据

QA实际执行nft JSON读回，不仅相信proof文件。app及ingress均为inet qa_guard三条链，hook优先级-150、input/output/forward默认DROP。PID1 UID四字段均65534，CapInh、CapPrm、CapEff、CapBnd、CapAmb全零，NoNewPrivs=1，rootfs只读。规则中的回包许可检查ct方向reply，固定新连接目的分别受角色限制。

重建后分别从非root进程探测IPv4公网/保留测试地址、IPv6测试地址、Docker127.0.0.11 TCP与UDP DNS、宿主桥地址及错误backend端口。均未连通；inet OUTPUT拒绝计数实际增加：ingress从0到6，app从0到4。部分公网/IPv6因无路由先拒绝，不能把这些单项都宣称由nft计数；但实际DNS及有路由拒绝与计数上升共同证明白名单边界执行。没有放宽出站或靠代理提示保证安全。

## A自检查缺口与互斥交接

nft1的应用规则只允许入口peer新入站和固定TLS网关新出站，没有应用自身127.0.0.1:8180例外。此为实际规则读回后的缺口评估；QA没有成功执行该自HTTP探测并保存响应，因此不伪称A已实际PASS或已有失败响应。

在确认仅两个completed合成任务、无活跃任务后，QA已通知Fix/主QA释放互斥backend地址给TLSclient。后续单次自探针时app已不可用，QA未为补报告重建或重启它，避免干扰真实云测试。

Fix可另以nft2仅在app角色增加严格loopback IPv4目的127.0.0.1:8180及对应input/reply条件，不能泛放整个lo、127/8、Docker stub DNS或其他端口。新镜像/规则冻结后，需在主QA云任务完成再恢复local进行A及负向定向复验；nft1的B/C通过不自动扩展为新镜像通过。

## 证据与结论

原始日志、完整容器信息和私有运行配置仅在忽略目录。

| 证据 | 原始字节SHA256 |
| --- | --- |
| host/core/内核负向阶段summary | `224a5826f1ac51124b80a532943e4b6298e145808bfab915609251fa98c7f33c` |
| restart/recreate阶段summary | `709a2993b3733fcf37ea94eaa6dacee8e4f58dba4638ee7c7639571249683f77` |

本地索引分别为 `persistent-ingress-b9cab9df6a`、`persistent-ingress-590b741b13`。后一结果已有active_tasks_at_end=0，恢复断点时再次只读确认仅completed2，不保持地址占用等待写报告。

结论：**持久入口B/C、core、Docker重启重建及隔离检查通过；A自检查PENDING，Windows整机重启NOT_TESTED**。不会把restart=unless-stopped当作Windows重启实测。用户日后重启Windows且Docker Desktop就绪后，应先查看独立项目状态，再执行 `Test-NetConnection 127.0.0.1 -Port 8180` 和 `Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8180/`；若此前为真实云切换停止了local应用，应先按已审启动脚本显式恢复local。不得通过再次临时中继冒充持久入口恢复。

## nft2 最小loopback修复后的独立定向复验

主QA确认云client只有空闲进程并安全停止释放互斥地址后，QA恢复local应用和入口，未操作TLS网关、源文件或云请求ledger。

- 配置：`0683a17b6bae2b00fbe8fe31e931475122a1e731`。
- 镜像：`sha256:5ee2e281796686b781e585593c0d8552c92efe25f1782545eacc2fe05368199c`，新标签nft2，不覆盖nft1。
- 业务快照仍为 `67709c4989781594dd6c4723666fdb2c21caaa7b`。

仅app角色增加lo接口且源/目标均127.0.0.1、目的8180的最小许可；没有放行整个loopback网段或Docker DNS。实际检查结果：

| 定向复验 | 结果 |
| --- | --- |
| A app内非root真实HTTP到127.0.0.1:8180 | PASS，200 |
| Windows host根页面、无认证info、认证info | 200、401、200 |
| 127.0.0.1:8181、127.0.0.2:8180、127.0.0.11 TCP53 | 均拒绝，OUTPUT drop计数增加 |
| Docker stub UDP53、IPv4/IPv6公网、其他端口/宿主桥探测 | 均未连通，nft拒绝计数增加 |
| 两角色实际nft链、默认DROP、-150优先级、PID1五组cap全0/非root/NNP1 | PASS |
| 仅app force-recreate后A与host恢复、实际规则重装与cap0 | PASS，app容器ID实际变化 |

首次定向请求抢在应用完成启动之前收到connection refused，脚本当即保留PARTIAL证据；补齐QA等待现有host就绪后再次执行相同源码，以上定向通过，没有修改业务或为测试放宽规则。

nft2只改变最小网络规则，所以本轮复用nft1同业务源码已完成的合成完整core、Docker restart/recreate与幂等持久性证据，没有重跑191方法或真实模型。本段没有把nft2未重复的完整解析行为伪称为重新执行。

测试后只读确认active_tasks=0，QA正常停止local app并立即通知Fix/主QA，释放地址给后续云client；ingress保持运行，停止local app是明确资源交接，不是服务故障。没有强杀任务或修改云ledger。

本地 `persistent-ingress-f14c53adcb/summary.json` 原始字节SHA256：`1abed23d231dec06e29034ba4a11f5eb4966b19f9495f16c7d2d12f019de88c0`。

更新结论：**独立持久local入口A/B/C及最小隔离边界已通过；Windows整机重启仍NOT_TESTED**。当前若云client占用同地址，local app保持停止；云任务完成后需用已审脚本显式恢复local，再由用户执行Windows重启后的实际检查，不能把unless-stopped或容器重建结果扩称为整机重启通过。
