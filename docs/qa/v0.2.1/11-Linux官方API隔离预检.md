# Linux 官方 API 隔离预检

用户已明确批准独立 Linux 测试环境；它与 Windows SAC 分离，不修改或绕过 Windows 策略。此阶段尚未真实上传，版本保持 BLOCKED。

## 已完成的低成本实测

复用既有固定镜像 `sha256:b4010953b65e06c2d1000fdcd129f6fcceeed9b9a5d48a12266d3365a610a2b1`，没有拉取、安装或下载模型。Python 3.12.16、OpenSSL 3.0.22，系统 CA 可读，httpx/requests 已安装。镜像也有 Paddle/sklearn 包，但诊断未导入这些包，未挂载模型。镜像没有 nft、iptables、ip 或 curl；已有 openssl/getent。

仅按用户授权向 Google 做基础 DNS/TLS 探测：DNS 成功，TLS 1.3 握手与证书校验 PASS，未发送真实语料、Token 或官方 API 请求。该结果只说明基础 Linux HTTPS 可用，不代表 MinerU API、任意外网权限或最终隔离已经通过。

当前私有清单仍为原 batchID、固定 19 个 SHA 和统一期限，过期时间 2026-11-09 10:42:13 UTC；检查时尚有效，无请求 usage 账本。首批仍限原 S00014、S00007、S00010，共 13 页。不得自动延长清单或新建批次重置 32 调用/3 内容预算。

## 准备中的最小执行边界

- 客户端仅接独立 internal Docker 网络，自身不能直接访问公网或提供通用 DNS；只读挂载精确业务源码、批准原文件和私有清单，原持久账本可写；不挂模型。Key 通过进程内存输入，不写镜像、命令行、日志或代理。
- 网关不挂 Key、语料、业务源码或模型。用户随后明确授权补齐缺少的镜像依赖，Fix正在按固定 Dockerfile/包版本准备共享最小 nft 镜像；QA不重复安装或构建。
- 受信 init 只解析固定三个官方域名并核查所有 IPv4/IPv6 结果为公网；记录 pins。双栈 OUTPUT 默认 DROP，只允许这些固定公网 IP 的 TCP 443 新连接及必要回包；启动解析后关闭通用 DNS。先装规则，再降到非 root、capabilities 为零；失败不监听。
- 标准 CONNECT 入口仅接受 `mineru.net:443`、`mineru.oss-cn-shanghai.aliyuncs.com:443`、`cdn-mineru.openxlab.org.cn:443`。拒绝 IP 字面量、其它域/端口、URL、用户信息、异常或歧义头。运行期只连接已审核 IP，不重新解析客户端目标。没有自写 TLS ClientHello 解析或 TLS 终止；官方客户端继续验证服务器证书。
- QA 运行器通过现有 client_factory 注入显式 httpx proxy transport，保留 OfficialMinerUClient 的固定来源/跳转检查、真实 SHA、TEST_BATCH、每请求授权和原持久计数。客户端是受控固定源码，不接收用户任意程序；官方方法/路径仍由现有客户端限定。不裸调用客户端绕过授权。

## 当前 Mock 和可复现入口

新增 `tests/test_v021_linux_egress_policy.py` 的 8 个纯函数方法已实际 8/8 PASS，0 网络。覆盖固定主机、恶意后缀、IP/端口、URL、歧义头、私网/loopback/link-local/IPv6、缺失 pins 等。命令：

```powershell
python -B -m unittest tests.test_v021_linux_egress_policy -v
```

代理 helper `tests/qa_mineru_egress_proxy.py` 默认只做权限/证明检查，不监听；明确 `--serve` 才启动。准备的容器内 dry-run 命令为：

```text
python /qa/qa_mineru_egress_proxy.py --pins /policy/pins.json --attestation /policy/kernel-attestation.json --client-ip <固定内部客户端IP>
```

此命令要求受信 init 生成的当前 netns、双栈 DROP、无通用 DNS、精确固定 IP/443 与 root 持有且非受信不可写的证明，且当前非 root/cap0。当前证明与 nft 镜像尚未形成，不能将纯函数 PASS 说成内核隔离或该命令已执行成功。

独立云端 runner 为 `tests/qa_mineru_linux_runner.py`。源代码49个Python文件的SHA256索引已从冻结Git提交生成；不改业务代码。准确的容器内dry-run入口如下，不带 `--execute`，不读取Key、不发官方请求：

```text
python /qa/qa_mineru_linux_runner.py --attestation /policy/client-kernel-attestation.json --integrity /policy/linux-source-integrity.json --plan /policy/preflight-plan.json --manifest /policy/manifest.json --registration /policy/canonical-ledger-registration.json --ledger /ledger/manifest.json.usage.json --output /output --gateway-ip 172.30.250.11
```

只有协调器收到独立内核读回、实际负向探针和dry-run证据后才追加 `--execute`；Token仅经stdin输入内存，不写命令行或Docker环境元数据。该runner保持原真实DocumentParser和正式授权/预算链，额外禁止本次纯云环境导入模型包，429或不确定POST后阻止新发送。原始失败候选和官方结果只保留在私有output；代理仅见匿名来源，不打印签名URL。runner目前仅语法检查通过，未宣称真实执行已通过。

最小权限账本布局经协调器确认：只在证明旧账本不存在、真实请求为0后首次登记专用batch-ledger目录下唯一账本，批次/owner/32调用3内容上限不变，不重置已有账本。仅该专用目录RW挂载，其余私有文件逐一只读；active记录canonical路径，runner要求登记信息一致并禁止默认旧路径另开账本。

实际上传前仍须验证：客户端 IPv4/IPv6 直连和通用 DNS均失败；网关任意外域/端口和伪造 CONNECT 均失败；允许官方域仅443且标准TLS证书校验通过；网关自身cap0且内核规则确实限制新出站；无主机端口或业务网络暴露；HTTP重定向到新域拒绝。由协调器审核这些证据后再启动同清单的真实云端。

## 纯云对照的本地状态

最新业务源码 67709c4989781594dd6c4723666fdb2c21caaa7b 的真实 DocumentParser 可用于 remote 策略。PaddleRuntime 先校验模型文件，再创建 worker/导入 Paddle；Linux不挂模型时会在导入前真实失败，不下载，不用 FakeParser。Native 可解析页照常保留，本地失败候选也保留；缺模型属于本环境本地 BLOCKED，不是完整双引擎 PASS。该 IngestionError 是否有结构化附件按实际结果报告，不伪造分类或本地预测。

Windows auto 任务零 POST 证据继续保留；Linux任务必须另记源码和环境指纹，保持同一 batch/owner、原账本和稳定任务策略键。纯 remote 成功只能叫独立 MinerU 对照，不能算自动回退或本地 OCR 已通过。遇429、预算耗尽或不确定POST停止，不换批次、不加额度、不盲目重发。
