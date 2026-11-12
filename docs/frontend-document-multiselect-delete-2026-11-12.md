# 文档管理页：多选与删除能力（2026-11-12）

> 分支：`feat/frontend-api-v0.2.2`（仅本地提交）
> 状态：**源码交付 / 静态与构建验证通过 / 浏览器交互与真实删除未验证**
> 性质：前端自修，不改后端源码、数据库、Docker 镜像、正式 8180 容器与数据卷。

## 1. 需求与契约核查

用户截图定位在「文档列表 REAL」卡片，要求增加**多选操作**与**删除选项**。实施前先核对删除能力是否真实存在：

| 核查对象 | 结果 |
|---|---|
| v0.2.3 离线契约 `docs/integration/frontend-openapi-v023.json`（29 路径） | `/api/documents/{file_id}` **仅 GET**；整份契约**没有任何 `delete` 方法** |
| v0.2.2 运行契约（22 路径） | 文档相关路径同样只有 `GET /api/documents`、`GET /api/documents/{file_id}`、`GET /parse-history`、`POST /api/parse/files`、`GET /source` |
| 后端 Python 源码 | 无业务文档删除路由；唯一出现 DELETE 的位置是 `deploy/frontend/server.py` 的静态网关通配转发，与业务删除无关 |
| 页面既有约束 | 「原始证据文件只读」「解析结果与原始文件通过后端 SHA256 绑定」，前端不修改原始文件 |

**结论**：后端当前不提供文档删除接口。因此不能实现"真实删除后端记录"，也**绝不能用本地隐藏行 / 本地移除数据来伪造删除成功**。本轮把多选做成真实可用，删除做成方法级运行期门控，并把接口需求交给 Agent C。

## 2. 本轮改动

| 文件 | 改动 |
|---|---|
| `src/components/MrProTable.vue` | 新增可选 `selectable` prop（默认 `false`，其他页面行为不变）、`type="selection"` 列、`selection-change` 事件、`clearSelection()` expose；`watch(rows)` 在分页 / 查询 / 刷新后清空选择，避免对已不存在的行执行批量操作 |
| `src/api/dataSource.ts` | 新增 `runtimeMethodPaths` / `collectRuntimeMethodPaths()` / `hasRuntimeMethod(method, path)`，从运行期 `/api/openapi.json` 解析 `METHOD path`；`resetContractState()` 同步清空；`MISSING_CAPABILITIES` 补 `DELETE /api/documents/{file_id}` |
| `src/api/frontend.ts` | 新增 `deleteDocument(fileId)`，只由门控通过的页面调用，注释明确"请求被接受 ≠ 已从列表消失" |
| `src/views/DocumentsView.vue` | 文档列表多选 + 选中批量条 + 批量下载原件 + 单行/批量删除门控；上传卡片多选 + 「移出待创建」；操作列宽度 270→330；新增批量条与提示条样式 |
| `docs/agent-c-backend-improvement-handoff-2026-11-12.md` | A 类新增 `DELETE /api/documents/{file_id}`（可选批量删除）需求与验收要求 |

### 2.1 删除门控（方法级，不是路径级）

```
canDeleteDocuments = hasToken() && hasRuntimeMethod('DELETE', '/api/documents/{file_id}')
```

`/api/documents/{file_id}` 路径存在只说明有 GET；若沿用旧的 `hasRuntimeRoutes()` 路径集合判断，会错误解锁删除按钮。因此新增方法级比对。当前正式 8180 的契约未声明该 DELETE 方法，页面表现为：

- 单行「删除」与「删除选中（N）」**禁用**，鼠标悬停显示 `unimplementedHint('DELETE /api/documents/{file_id}')`；
- 列表上方常驻一条 warning 提示，说明禁用原因与解锁条件；
- 选中行不会从前端本地数组移除，不做任何"假成功"。

后端实现并在 `/api/openapi.json` 声明该方法后，前端**无需改码**即自动解锁：确认弹窗 → 逐个调用真实 `DELETE` → 仅按 2xx 统计"请求被接受" → 重新 `GET /api/documents` 刷新列表 → 清空选择。失败按 `apiErrorHint` 如实提示，不隐藏错误。

### 2.2 多选现在就能用的动作

| 动作 | 真实能力 | 说明 |
|---|---|---|
| 勾选 / 全选（当前页） | 前端 | 仅当前页；翻页、查询、刷新自动清空 |
| 取消选择 | 前端 | 清空勾选 |
| 批量下载原件 | `GET /api/parse/files/{id}/source` | 顺序下载，成功/失败分别计数，不吞错 |
| 删除选中 | 门控 | 当前 8180 禁用，见 2.1 |
| 移出待创建（上传卡片） | 纯本地会话队列 | 弹窗明确：仅从「本次会话真实上传」待创建列表移除，**不删除后端已上传原始文件、不取消已创建任务** |

## 3. 验证结果

| 项 | 结果 |
|---|---|
| `npm run typecheck` | 退出 0 |
| `npm run build` | 退出 0；产物 `index-a9d8defe.js`、`DocumentsView-0d9d37db.js`、`MrProTable…c62c3998.js`（仅既有 >500 kB 告警） |
| `git diff --check` | 无错误 |
| 敏感词扫描（4 个改动源码） | 无凭证、DSN、MinerU Key、机器绝对路径 |
| 4173 预览 | `/documents` 200，首页引用 `index-a9d8defe.js`，新 `DocumentsView` / `MrProTable` chunk 均 200；`/api/openapi.json` 未带凭证 401（代理指向 8180） |
| 产物关键文案 | 「删除选中」「批量下载原件」「移出待创建」「DELETE /api/documents」均已打包 |

**未执行**：浏览器交互实测、任何真实 `DELETE` 调用、正式 8180 上的上传/创建/删除写操作。因当前契约不存在删除方法，删除正向链路无法在本机验证；状态不是 `READY_FOR_FINAL_QA`，更不是 QA PASS。

## 4. 交给 Agent C / QA 的事项

1. 实现 `DELETE /api/documents/{file_id}`：认证与 owner 隔离、幂等语义、软删除或物理删除口径、关联解析任务与原始字节的处置、错误码（403 / 404 / 409 / 422）。
2. 在 `/api/openapi.json` 中**声明 DELETE 方法**（前端门控依赖方法而非路径存在）；如需批量，可另提供 `POST /api/documents/batch-delete`，前端当前按逐个 DELETE 实现。
3. QA 在隔离实例验收：删除后列表真实消失、跨 owner 403、重复删除语义、失败时前端不显示成功、刷新后状态一致。

## 5. 边界

未改后端源码、数据库结构与数据、正式镜像、8180 容器、数据卷、ACTIVE 版本；Token 仅存内存 + `sessionStorage`；未 Push / Merge main / 打 Tag / 部署生产。4173 为独立预览，8180 共享容器保持冻结。
