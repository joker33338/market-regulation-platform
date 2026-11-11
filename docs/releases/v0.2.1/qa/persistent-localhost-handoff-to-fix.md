# 持久 localhost 入口：QA → Fix 最小配置交接

日期：2026-11-09。源码基线：`67709c4989781594dd6c4723666fdb2c21caaa7b`。这里只定义独立配置和验收，不修改业务代码或原始 main 工作树；不把已通过的限时中继当作持久入口。

## 实测约束与环境缺口

现有 internal-only QA 容器没有默认网关，Docker保存127.0.0.1:8180请求却不生成实际发布映射。根因和上游说明见 `10-localhost-network-diagnosis.md`。普通第二网络会引入出站，不可直接采用。

固定基础镜像 `sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1` 为Debian12/Python3.12.16，有setpriv 2.38.1、libcap、libseccomp2 2.5.4，但没有nft、iptables/ip6tables、libnftables/libnftnl/libmnl、nginx或socat。已有Python可运行固定反代，无需引入大型代理框架。

需要先由用户明确批准：**仅为独立新网关镜像安装nftables及必需运行库**。不修改原b401、Windows宿主、原应用或模型环境。批准前不build/pull/install，不自行授予NET_ADMIN运行。已有持久方案授权不能被解释为已批准未提出的具体包安装。

## Fix文件职责与接口

| 建议文件 | 职责 |
| --- | --- |
| `deploy/qa-gateway/Dockerfile` | 固定b401基础，安装唯一必要nft包及锁定依赖，记录来源/包清单/构建digest |
| `deploy/qa-gateway/package-lock.json` | 官方Debian签名仓库、包版本/架构/哈希及依赖闭包；未解析条目阻止构建 |
| `deploy/qa-gateway/init.sh` | 无secret启动，安装并检查规则、关闭转发、再降UID和所有cap，失败立即退出 |
| `deploy/qa-gateway/ingress.nft` | 固定backendIP:8180、双栈默认拒绝、计数器，不做NAT或flush全局规则 |
| `deploy/qa-gateway/fixed_proxy.py` | 仅固定上游HTTP反代，不提供CONNECT/SOCKS/动态URL，不记录请求体和Token |
| `compose.qa-localhost.yaml` | 独立project，不使用默认Compose；应用仅internal，网关双网络并只发布127.0.0.1:8180 |

配置文件由Fix实现。QA仅增加对应安全测试和消毒报告。主QA的Linux TLS/MinerU专用网关复用同一最小基础镜像，规则角色分开，不能把官网IP白名单加到本地入口角色。

## 新网关镜像的固定依赖

已查询官方Debian Bookworm元数据：nftables与libnftables1均为 `1.0.6-2+deb12u2`；libnftnl11为 `1.2.4-2`。nft的必要闭包包括libedit2、libnftables1以及后者的libgmp10/libjansson4/libmnl0/libnftnl11/libxtables12。libc6在基础镜像已存在，不借机升级已有环境。

来源：[nftables](https://packages.debian.org/bookworm/nftables)、[libnftables1](https://packages.debian.org/bookworm/libnftables1)、[libnftnl11](https://packages.debian.org/bookworm/libnftnl11)。当前尚未下载/安装或解析完整闭包锁；Fix须先完成所有实际版本与包哈希锁定、展示差异，不能用未固定的latest或无约束升级凑构建。最终镜像ID与完整dpkg清单作为执行证据，基础镜像ID不变。

## 独立Compose最小设计

拟使用未与当前Docker网络重叠的backend `172.30.250.0/28`、frontend `172.30.251.0/28`；这只是只读盘点时的候选，创建前仍须重新检查Docker网络与宿主路由冲突，冲突立即停止，不改已有网络。

应用固定backend `172.30.250.10:8180`，只连internal backend，无host发布、无默认网关、源码只读快照。入口网关固定backend地址和独立普通frontend，仅网关发布 `127.0.0.1:8180:8180`。网关不挂应用Token、数据库DSN、语料、源码、Docker socket，仅挂静态规则/固定代理配置；不使用host network或privileged。配置restart=unless-stopped，read_only、tmpfs、资源限额与安全选项继续保留。

后端仍为真实create_app factory，是否启用Mock或真实业务配置由明确任务决定，不在网关中放宽上传许可。代理不处理、不改写授权逻辑。

## 内核限制：先规则，后降权，再监听

独立网关初始化只增加NET_ADMIN；若setpriv降UID确需SETUID/SETGID，只允许初始化最小组合并在交接前显示cap位图，不默认给额外能力。没有规则成功的时间窗口不得开始监听或读取secret。无现成代理连接需继承。

本地入口规则设计（需真实nft语法/内核验收后才能称有效）：

```nft
table inet qa_gateway {
  chain output {
    type filter hook output priority 0; policy drop;
    ct state invalid counter drop
    ct direction reply ct state established counter accept
    ip daddr 172.30.250.10 tcp dport 8180 ct state { new, established } counter accept
    counter drop
  }
  chain forward {
    type filter hook forward priority 0; policy drop;
    counter drop
  }
}
```

inet覆盖IPv4与IPv6，IPv6没有新连接许可；禁止DNS/UDP、任意公网IP、metadata、宿主其他服务。回包只允许ct方向reply，不能用无方向的ct established泛放。也不能把反代参数约束当作防火墙。固定IP消除DNS例外。禁止在应用命名空间或宿主flush规则。

关闭网关IP转发，不能作为路由器。nft安装后用setpriv切换非root，清除bounding/inheritable/ambient并启用no-new-privs；代理启动时实际核对 `/proc/self/status` 的Uid、CapInh/CapPrm/CapEff/CapBnd/CapAmb全部为零（UID非零，NoNewPrivs=1），任何不满足则退出，不以日志声称成功。验证nft规则仍生效，非root不能改规则。

## 与Linux TLS/MinerU角色共用而不混权

主QA负责 `approved-egress` 角色的固定三域、TLS SNI/证书与authorizer合同；只共用镜像和初始化能力。它的公网地址只能由受审启动阶段一次解析并输出无secret的已批准IP清单，随后DNS权限撤销、过期拒绝；网关不挂Key/语料，client仅internal且不能绕过网关。具体域名/配置交由主QA，不在本handoff猜测或扩展。

本地入口 `local-ingress` 始终只准固定backend8180；两个角色不同规则、不同网络、不同容器，不把公网443例外混到本地入口。

## 最小验收与真实限制

1. 构建前包安装范围获批准；构建显示基础digest、闭包锁和最终imageID，不重新安装模型或全量依赖。
2. 初始化失败时不监听；降权后五组cap全部0、UID非root；规则存在、非root篡改被拒。
3. 内部、同网peer、Windows Test-NetConnection/IWR、认证/合成上传/Mock解析/结果/幂等、restart持久性各自记录，不能只exit0认PASS。
4. 允许固定backend8180，同时从网关验证IPv4/IPv6新出站、DNS、其他端口/宿主被拒；读取拒绝计数，不仅依赖超时。启动前的未准外连不能因ct established规则残存。
5. 应用仍只有internal网络且无默认网关，网关FORWARD被拒；不挂socket、不改Windows防火墙。应用与网关重建/重启后规则重新先安装再服务，依赖缺失fail closed。
6. HTTP静态页面/OpenAPI关闭状态与PG连通分别验证，网关不自动连接未知数据库；不重跑191方法或真实模型。
7. Windows整机重启必须由用户完成。restart policy与Docker restart只能证明各自范围，不能伪造Windows重启实测。

## 最新用户授权与客户端DNS强制边界

用户随后明确允许下载、构建、安装必要独立镜像，因此以上“构建前待批准”条件现已满足。Fix可实施新独立镜像，不需要继续等待安装许可；仍必须固定来源、版本、最终digest，不覆盖b401、原应用或宿主依赖。当前状态为 **READY_FOR_FIX_IMPLEMENTATION**，不是已完成或PASS。

主QA补充的关键边界：Docker internal并不等于禁止嵌入式DNS转发，不能只配无默认网关或普通dns字段。Linux测试client自己的网络命名空间也需要内核OUTPUT默认DROP，仅允许ct REPLY回包及固定TLS网关IP:端口的新连接，不允许127.0.0.11/任意DNS、任意UDP/TCP公网。应在OUTPUT DNAT之前的过滤优先级执行固定允许规则，或证明Docker DNS重写后也无法绕过。必须实际探测Docker嵌入式DNS与公网直接连接，并读取内核拒绝计数。

客户端如需NET_ADMIN，仅可信初始化短暂持有，然后非root且CapInh/Prm/Eff/Bnd/Amb均清零，再启动应用/测试客户端。初始化失败不得加载私有凭据或开始监听；私有授权、语料和Key不进入网关。具体TLS网关端口由主QA协议helper指定并静态锁定，不能猜测或允许任意host/port。此客户端规则与入口proxy规则是不同角色；固定入口仍只允许backend8180，不能把公网白名单或DNS许可混入入口。

实施限定为独立测试服务，不是生产部署。Windows真实整机重启仍须用户执行，不能自行重启机器或以Docker restart替代。
