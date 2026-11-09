# 独立本地QA入口与Linux官方测试环境

固定Docker Desktop分组：`market-regulation-qa-localhost`。
本地应用与入口镜像：`market-regulation-qa-gateway:v0.2.1-nft2`。
云测试网关与客户端继续固定 `market-regulation-qa-gateway:v0.2.1-nft1`，不因本地自检更新被重建。
原有 `market-regulation` 分组、镜像、数据库、模型和Windows策略不受本配置修改。
这是独立测试服务，不是生产部署；两个profile均默认关闭。

## 日常操作

在本版本Fix工作树打开PowerShell，运行以下命令。脚本会自行定位工作树，不需要复制测试资料或输入密钥。
首次已构建后直接启动；重建只在需要更新独立工具镜像时使用，不自动中断正在运行的容器。

```powershell
./scripts/qa-localhost.ps1 -Action start
./scripts/qa-localhost.ps1 -Action status
./scripts/qa-localhost.ps1 -Action stop
./scripts/qa-localhost.ps1 -Action rebuild
```

入口固定为 `http://127.0.0.1:8180`，仅发布Windows回环地址。
默认运行匿名Mock，实际应用仍使用真实FastAPI factory与原认证机制；不会自动调用官方API或模型。
普通start发现已有服务时只显示状态，不重建它；先完成任务再stop/start以重新加载配置。
脚本仅操作这个Compose分组，不操作原服务，也不强制结束其它QA/Fix任务。

本地配置在当前工作树 `local/qa-localhost/`，全部被Git忽略：

- `runtime.json`：首次生成随机API Token，不能粘贴到Git、报告或聊天；网关不读取此文件。
- `source/` 与 `source.commit`：业务源码固定 `67709c4989781594dd6c4723666fdb2c21caaa7b`，只读挂载。
  复制的只是Git内的代码，逐业务Python核验规范化换行后的内容，不包含原始测试集或模型。
- `state/`：独立临时任务与SQLite，不访问PostgreSQL。
- `output/`：独立云验证的私密输出；不会由普通start读取或上传。

可以用 `-Python` 指定已有Python；默认读取Git公共目录的本地 `agent-local.json` 中 `originalRoot`，
只复用原虚拟环境执行低成本配置检查，不改环境、不安装Python依赖。
缺少镜像时先rebuild；只下载锁定的6个nft依赖包，官方签名索引与各包SHA256记录在 `package-lock.json`。
已有基础镜像的151个包必须匹配且保持不变，否则构建拒绝。

## 网络与权限约束

入口 `.12`、应用/独立客户端 `.10`、TLS网关 `.11` 使用独立backend `172.30.250.0/28`；
入口frontend为 `172.30.251.0/28`，TLS出口为 `172.30.252.0/28`。
脚本先检查宿主路由与已有Docker网络重叠；冲突时停止，不修改已有网络。
应用或客户端仅连接internal backend，没有对外默认路由；所有角色仍有自己的内核规则，不能仅靠internal宣称隔离。

每个容器只在初始化期拥有NET_ADMIN/SETPCAP/SETUID/SETGID。
先校验并安装本命名空间inet默认DROP规则，再读回规则、关闭转发、生成root只读证明；
随后exec降为65534，清空五组capabilities并开启NoNewPrivs，检查通过才监听或读取应用配置。
不保留root父进程。没有docker.sock、host network、privileged或原数据卷。
OUTPUT优先级-150处于连接跟踪之后、Docker DNS目的地址转换之前，运行期DNS和任意直连均拒绝。
入口仅允许固定应用8180，客户端仅允许固定TLS网关8080；回包只准ct方向reply。
仅app角色额外允许lo接口上源/目标都为127.0.0.1、目的端口8180的自检连接；
不允许127.0.0.11、其他回环地址或其他端口，网关和云客户端没有此例外。
独立QA仍须读回实际规则、核对进程权限及拒绝计数，证明文件不能代替验收。

## 独立云验证

普通入口命令不启用cloud profile、不接收云Key，也不自动外传。
云测试由QA在本地任务完成后停止app，显式切到同IP的client；二者不能同时运行。
TLS网关启动时只解析固定三域，校验全部为公网IP，再禁止运行期DNS；只转发固定域的443 CONNECT。
客户端验证TLS/SNI/证书，网关没有密钥、源码、资料或数据库挂载。
固定地址窗口为30分钟，到期网关停止且不会自动刷新；恢复必须由QA显式重新初始化，沿用同批次原账本。

QA runner使用已提交的 `qa_mineru_linux_runner.py`，通过stdin仅在内存接收Key。
只单文件只读挂载批准的manifest、plan、source-integrity、registration与3个匿名输入；
仅专用原canonical ledger目录挂到 `/ledger` 可写，不能挂整个私有证据目录，不得建立第二份账本。
沿用既有SHA/TEST_BATCH授权与32调用、3唯一文件、单文件8调用预算，429或不确定POST安全停止。
网关启动成功与普通Mock通过不能表示真实API已通过，更不能表示真实Paddle或双引擎已可用。

## 重启边界

app与入口使用 `unless-stopped`，只表示Docker引擎运行时的容器恢复策略。
cloud没有自动重启，避免到期窗口被无限刷新。Docker restart/recreate与Windows整机重启须分别记录。
当前没有执行Windows整机重启。Docker Desktop登录自动启动的本地设置存在不一致，
请用户在Desktop界面确认登录启动；不由脚本修改注册表、Desktop设置或重启机器。
Windows自行重启后运行status，再检查固定入口。不能把容器重启测试当作整机重启证据。
