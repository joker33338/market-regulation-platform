<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">系统监控</h1>
        <p class="page-desc">真实健康检查五态 · 运行期契约探测 · API Token 会话配置 · 接口能力清单</p>
      </div>
      <el-tag type="success" effect="plain">{{ releaseStatus.shortLabel }}</el-tag>
    </div>

    <!-- 旧解析服务真实探活 + Token 会话配置 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>后端解析服务（FastAPI）<span class="real-badge">REAL</span></span>
          <el-button size="small" @click="store.probeBackend()">重新探测 /api/parse/info</el-button>
        </div>
      </template>
      <div class="conn-row">
        <span class="mr-state-tag" :class="`mr-state-${store.apiState}`">
          <span class="status-dot" :style="{ background: stateColor }" />{{ store.apiState }}
        </span>
        <span class="conn-note">{{ stateLabel }}</span>
      </div>
      <el-descriptions v-if="store.serviceInfo" :column="3" border size="small" style="margin-top: 12px">
        <el-descriptions-item label="provider">{{ store.serviceInfo.provider }}</el-descriptions-item>
        <el-descriptions-item label="mode">{{ store.serviceInfo.mode }}</el-descriptions-item>
        <el-descriptions-item label="enabled">{{ store.serviceInfo.enabled }}</el-descriptions-item>
        <el-descriptions-item label="dual_engine_enabled">{{ store.serviceInfo.dual_engine_enabled }}</el-descriptions-item>
        <el-descriptions-item label="database_enabled">{{ store.serviceInfo.database_enabled }}</el-descriptions-item>
        <el-descriptions-item label="字段来源">GET /api/parse/info（复用旧接口）</el-descriptions-item>
      </el-descriptions>
      <div v-else class="mr-disabled-hint" style="margin-top: 10px">
        尚未成功探测 /api/parse/info。后端不返回 version / environment 字段，本页不展示不存在的版本与环境信息。
        此探活结论只代表旧解析接口，不能推断 v0.2.2 新接口是否加载。
      </div>

      <el-divider />

      <div class="token-form">
        <el-input
          v-model="tokenInput"
          type="password"
          show-password
          placeholder="粘贴 PARSING_API_TOKENS_JSON 中配置的 Token（≥32 位）"
          style="max-width: 480px"
          @keyup.enter="saveToken"
        />
        <el-button type="primary" @click="saveToken">保存并验证</el-button>
        <el-button @click="store.logout()">清除会话凭证</el-button>
      </div>
      <div class="security-note">
        <div><b>开发期</b>：Token 仅存于<b>内存 + sessionStorage（会话级）</b>，关闭标签页即失效；不写 localStorage、不打印到控制台或日志；请求经 Vite 代理同源转发。</div>
        <div><b>生产环境</b>：应由服务端下发安全会话（HttpOnly Cookie / BFF），前端不长期持有访问 Token。</div>
        <div><b>密钥边界</b>：MinerU 官方 API Key、数据库口令一律只存在 FastAPI 后端，浏览器绝不接触；当前存储方式：{{ tokenStorageMode }}。</div>
      </div>
    </el-card>

    <!-- 运行期契约探测：源码已交付 ≠ 活动实例已加载 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>运行期契约探测 <span class="real-badge">REAL</span></span>
          <el-button size="small" :loading="probing" @click="reprobe">重新探测 /api/openapi.json</el-button>
        </div>
      </template>
      <div class="conn-row">
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain" size="large">
          {{ contractLabel[contractState] }}
        </el-tag>
        <span class="conn-note">
          OpenAPI 版本 <b>{{ contractMeta.version || '—' }}</b> ·
          契约名 <b>{{ contractMeta.contractVersion || '未标注' }}</b> ·
          运行期路径数 <b class="num">{{ contractMeta.pathCount }}</b> ·
          探测时间 <b>{{ formatTime(contractMeta.probedAt) }}</b>
        </span>
      </div>
      <el-alert type="info" :closable="false" style="margin-top: 12px"
        :title="contractMeta.hint"
        description="匿名 /openapi.json 被后端显式关闭；认证端点 GET /api/openapi.json 需要 Bearer Token。源码分支与离线快照只说明契约已交付，七个页面是否渲染真实数据一律以本探测结果为准；未就绪显示明确异常态，不回退 DEMO。" />
    </el-card>

    <!-- 当前登录人员：GET /api/auth/me（draft-2 新增，正式 8180 v0.2.2 未提供该接口） -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>当前登录身份 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            GET /api/auth/me · {{ principalState }}
            <el-button text size="small" type="primary" :loading="identityLoading" @click="refreshIdentity">重新确认</el-button>
          </span>
        </div>
      </template>
      <!-- 身份字段始终可见：旧实例未返回 /api/auth/me 时如实显示「未确认」，不隐藏字段、不编造值 -->
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="当前登录人员 principal_id">{{ principal?.principal_id || '未确认' }}</el-descriptions-item>
        <el-descriptions-item label="业务数据归属 owner_id">{{ principal ? (principal.owner_id || '无个人 owner（纯审核身份）') : '未确认' }}</el-descriptions-item>
        <el-descriptions-item label="角色 roles">{{ principalRoleText }}</el-descriptions-item>
        <el-descriptions-item label="凭证状态">{{ principal?.credential_status || '未确认' }}</el-descriptions-item>
        <el-descriptions-item label="审核范围 review_owner_scopes" :span="2">{{ principalScopeText }}</el-descriptions-item>
        <el-descriptions-item label="服务端权限 permissions" :span="2">{{ principalPermissionsText }}</el-descriptions-item>
        <el-descriptions-item label="数据范围 data_scope" :span="2">{{ principalDataScopeText }}</el-descriptions-item>
        <el-descriptions-item label="确认时间" :span="2">{{ formatTime(principalLoadedAt) }}</el-descriptions-item>
      </el-descriptions>
      <el-alert v-if="!principal" type="warning" :closable="false" style="margin-top: 10px" :title="`身份未确认（${principalState}）`"
        :description="principalError || 'GET /api/auth/me 未返回有效身份：该接口是否可用以运行期 GET /api/openapi.json 的方法级探测为准，未加载时不做身份推断。'" />
      <div class="mr-disabled-hint" style="margin-top: 8px">
        principal_id 是实际操作者，owner_id 是业务数据归属，两者不能互相推导，不能从 owner 反推人员。
        draft-4 起 ADMIN 拥有全部业务权限（data_scope=all，管理员的账号列表、运行日志与统计均为全局范围而非个人范围），
        USER 无审核写入能力；写操作以运行期契约、服务端权限与实际方法门禁为准，越界返回 404，无权返回 403。
        旧 owner→writers 授权说明自 draft-2 起不再适用。
      </div>
    </el-card>

    <!-- 组件五态：GET /api/system/health 真实响应 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>组件状态 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            GET /api/system/health · 总体 {{ health.data.value?.status || '—' }}
            <el-button text size="small" type="primary" style="margin-left: 8px" @click="health.load()">刷新</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="health.state.value" :error="health.error.value" empty-text="后端未返回组件状态" @retry="health.load()">
        <el-table :data="componentRows" size="default">
          <el-table-column prop="name" label="组件" width="160" />
          <el-table-column label="状态" width="170">
            <template #default="{ row }">
              <span class="mr-state-tag" :class="`mr-state-${row.state}`">
                <span class="status-dot" :style="{ background: stateColorOf(row.state) }" />{{ row.state }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="check" label="后端检查方式" width="220" show-overflow-tooltip />
          <el-table-column label="附加字段" width="200">
            <template #default="{ row }">
              <span class="mono">{{ row.extra || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="note" label="真实性说明" min-width="240" show-overflow-tooltip />
        </el-table>
        <div class="mr-disabled-hint" style="margin-top: 10px">
          仅 fastapi（请求被处理）、task_store 与 postgresql（只读查询成功）可为 ONLINE；本地模型仅文件检查 → UNKNOWN，
          MinerU 仅配置检查 → UNKNOWN / NOT_CONFIGURED。后端不返回 DSN、Token、模型路径或异常堆栈；
          前端不主动调用 MinerU 云端验证凭证，也不把 HTTP 200 解释为全部底层服务正常。
        </div>
      </AsyncPanel>
    </el-card>

    <!-- v0.2.2 接口能力清单：源码契约 + 明确不支持 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>接口接入状态总览 <span class="real-badge">REAL</span></span>
          <span class="card-sub">
            契约 {{ CONTRACT_ROUTES.length }} 行 · v0.2.3 新增 {{ CONTRACT_ROUTES_V023.length }} 行 · 明确不支持 {{ MISSING_CAPABILITIES.length }} 组 ·
            {{ releaseStatus.apiContractReview }}
          </span>
        </div>
      </template>
      <el-tabs v-model="apiTab">
        <el-tab-pane :label="`源码契约（${CONTRACT_ROUTES.length}）`" name="routes">
          <el-table :data="CONTRACT_ROUTES" size="small">
            <el-table-column prop="method" label="方法" width="100" />
            <el-table-column prop="path" label="路径" min-width="300" show-overflow-tooltip />
            <el-table-column prop="page" label="使用页面" min-width="220" show-overflow-tooltip />
            <el-table-column label="来源" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="row.group === 'legacy' ? 'info' : 'success'" effect="plain">
                  {{ row.group === 'legacy' ? '复用' : '新增' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="运行期" width="110">
              <template #default>
                <span :class="contractState === 'ready' ? 'run-ready' : 'run-pending'">
                  {{ contractState === 'ready' ? '契约就绪' : '待探测' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane :label="`v0.2.3 新增（${CONTRACT_ROUTES_V023.length}）`" name="v023">
          <el-table :data="CONTRACT_ROUTES_V023" size="small">
            <el-table-column prop="method" label="方法" width="100" />
            <el-table-column prop="path" label="路径" min-width="300" show-overflow-tooltip />
            <el-table-column prop="page" label="使用页面" min-width="220" show-overflow-tooltip />
            <el-table-column label="运行期" width="130">
              <template #default="{ row }">
                <span :class="runtimeHas(row.path) ? 'run-ready' : 'run-pending'">{{ runtimeHas(row.path) ? '已加载' : '未加载' }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="mr-disabled-hint" style="margin-top: 10px">
            源码契约依据草稿至 draft-4 的累积路由；路径数与能力以运行期 GET /api/openapi.json 实测结果为准，
            不写死任何版本号或路径总数。draft-1 的 owner→writers 授权说明已不适用；
            未加载的路由对应功能保持禁用 / 空态，不调用不存在的接口。
          </div>
        </el-tab-pane>
        <el-tab-pane :label="`待运行期验证（${MISSING_CAPABILITIES.length}）`" name="missing">
          <el-table :data="MISSING_CAPABILITIES" size="small">
            <el-table-column label="优先级" width="90">
              <template #default="{ row }">
                <el-tag :type="row.priority === 'P0' ? 'danger' : 'info'" size="small" effect="plain">{{ row.priority }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="api" label="接口" min-width="320" show-overflow-tooltip />
            <el-table-column prop="usage" label="对应业务" min-width="200" show-overflow-tooltip />
            <el-table-column prop="impact" label="前端处理" min-width="260" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>
      </el-tabs>
      <div class="mr-disabled-hint" style="margin-top: 10px">
        本表为源码契约清单（按方法列举 {{ CONTRACT_ROUTES.length }} 行），<b>不代表这些接口已在活动实例上探测成功</b>；
        活动实例的路径数、契约版本与能力以 /api/openapi.json 运行期探测为准，不沿用固定版本 SHA 或固定路径数；
        详细字段契约与实测结果见 frontend/docs/frontend-api-mapping-v0.2.2.md 与 frontend-api-integration-report.md。
      </div>
    </el-card>

    <!-- v0.2.3：API 进程真实资源 + 审核审计摘要（仅运行期契约加载后才请求） -->
    <el-card v-if="v023Monitoring" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>API 进程资源 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/system/resources · scope=api_process
            <el-button text size="small" type="primary" @click="resources.load()">刷新采样</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="resources.state.value" :error="resources.error.value" empty-text="后端未返回资源采样" @retry="resources.load()">
        <el-alert v-if="resources.data.value && !resources.data.value.available" type="warning" :closable="false"
          :title="`采样不可用：${resources.data.value.reason || '后端未给出原因'}`"
          description="失败时后端返回 available=false 与 null 指标，前端不把不可用伪装成 0 或正常。" />
        <el-descriptions v-else-if="resources.data.value" :column="3" border size="small">
          <el-descriptions-item label="memory_rss_bytes">{{ resources.data.value.memory_rss_bytes ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="cpu_user_seconds">{{ resources.data.value.cpu_user_seconds ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="cpu_system_seconds">{{ resources.data.value.cpu_system_seconds ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="uptime_seconds">{{ resources.data.value.uptime_seconds ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="threads">{{ resources.data.value.threads ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="sampled_at">{{ formatTime(resources.data.value.sampled_at) }}</el-descriptions-item>
        </el-descriptions>
      </AsyncPanel>
      <div class="mr-disabled-hint" style="margin-top: 8px">仅 API 进程真实采样：累计 CPU 秒不是利用率，不含宿主机、容器整体、GPU 或模型推理监控。</div>
    </el-card>

    <el-card v-if="v023Monitoring" shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>审核审计摘要 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/system/audit-logs · 按当前 principal 与审核范围
            <el-button text size="small" type="primary" @click="auditLogs.load()">刷新</el-button>
          </span>
        </div>
      </template>
      <AsyncPanel :state="auditLogs.state.value" :error="auditLogs.error.value" empty-text="当前身份范围内暂无审核事件摘要" @retry="auditLogs.load()">
        <el-table :data="auditLogs.data.value?.list || []" size="small" max-height="260">
          <el-table-column prop="action" label="动作" width="150" />
          <el-table-column prop="parse_id" label="parse_id" min-width="180" show-overflow-tooltip />
          <el-table-column label="操作者 operator_id" width="180"><template #default="{ row }">{{ identityText(row.operator_id) }}</template></el-table-column>
          <el-table-column label="文档所属人 owner_id" width="180"><template #default="{ row }">{{ identityText(row.owner_id) }}</template></el-table-column>
          <el-table-column prop="operator" label="兼容别名" width="150" show-overflow-tooltip />
          <el-table-column prop="version" label="版本" width="80" />
          <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
        </el-table>
      </AsyncPanel>
      <div class="mr-disabled-hint" style="margin-top: 8px">只展示真实审核事件摘要（approve / reject / mark-error / save-revision），不含修订正文；不编造未发生的历史事件。旧事件 operator_id / owner_id 为 null 时显示「未知（历史记录）」，不把历史 owner 补认成具体人员。</div>
    </el-card>

    <!-- v0.2.3 draft-4：运行日志（API / 错误 / 任务阶段），全部按运行期方法级门控 -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>运行日志 <span class="real-badge">REAL</span></span>
          <span class="card-sub">仅查询后端真实保存过的事件 · 不含凭证、查询串、请求正文或异常堆栈</span>
        </div>
      </template>

      <div class="log-filters">
        <el-date-picker v-model="logDateRange" type="datetimerange" value-format="YYYY-MM-DDTHH:mm:ss"
          range-separator="至" start-placeholder="起始时间" end-placeholder="结束时间" size="small" style="width: 340px" />
        <el-select v-model="logLevel" placeholder="level（仅 API / 错误日志）" clearable size="small" style="width: 200px">
          <el-option label="info" value="info" />
          <el-option label="warning" value="warning" />
          <el-option label="error" value="error" />
        </el-select>
        <el-input v-model="taskLogId" placeholder="task_id（任务阶段日志）" clearable size="small" style="width: 240px" @keyup.enter="loadAllLogs" />
        <el-button type="primary" size="small" @click="loadAllLogs">查询</el-button>
        <el-button size="small" @click="resetLogFilters">重置</el-button>
      </div>
      <div class="mr-disabled-hint" style="margin: 8px 0 4px">
        时间区间按 ISO 8601 带时区（UTC）发送；后端只查最近 10000 条窗口，truncated=true 时如实标注截断。
        ADMIN 为全局范围，其他身份仅本人请求，实际范围以响应 <code>scope</code> 为准；
        historical_backfill=false 表示不回填历史事件。三个列表各自独立分页。
      </div>

      <el-divider content-position="left">接口调用记录 · GET /api/system/api-logs</el-divider>
      <el-empty v-if="!routeApiLogs" :image-size="54" description="运行期未加载该接口，不展示演示记录">
        <span class="mr-disabled-hint">GET /api/openapi.json 未返回 GET /api/system/api-logs；源码契约已交付不等于活动实例已加载。</span>
      </el-empty>
      <AsyncPanel v-else :state="apiLogs.state.value" :error="apiLogs.error.value" empty-text="当前筛选范围内暂无 API 调用记录" @retry="apiLogs.load()">
        <el-table :data="apiLogs.data.value?.list || []" size="small" max-height="260">
          <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
          <el-table-column label="principal_id" width="180" show-overflow-tooltip><template #default="{ row }">{{ identityText(row.principal_id) }}</template></el-table-column>
          <el-table-column prop="method" label="方法" width="90" />
          <el-table-column prop="route" label="路由" min-width="240" show-overflow-tooltip />
          <el-table-column label="状态码" width="90"><template #default="{ row }"><el-tag size="small" :type="row.status_code >= 400 ? 'danger' : 'success'" effect="plain">{{ row.status_code }}</el-tag></template></el-table-column>
          <el-table-column prop="duration_ms" label="耗时 ms" width="100" align="right" />
          <el-table-column prop="level" label="level" width="90" />
        </el-table>
        <div class="mr-disabled-hint" style="margin-top: 6px">{{ logMeta(apiLogs.data.value) }}</div>
        <div class="queue-pager"><el-pagination v-model:current-page="apiPage" :page-size="logPageSize" :total="apiLogs.data.value?.total || 0" layout="total, prev, pager, next" small background @current-change="apiLogs.load()" /></div>
      </AsyncPanel>

      <el-divider content-position="left">错误日志 · GET /api/system/error-logs</el-divider>
      <el-empty v-if="!routeErrorLogs" :image-size="54" description="运行期未加载该接口，不展示演示记录">
        <span class="mr-disabled-hint">GET /api/openapi.json 未返回 GET /api/system/error-logs。</span>
      </el-empty>
      <AsyncPanel v-else :state="errorLogs.state.value" :error="errorLogs.error.value" empty-text="当前筛选范围内暂无错误日志" @retry="errorLogs.load()">
        <el-table :data="errorLogs.data.value?.list || []" size="small" max-height="260">
          <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
          <el-table-column label="principal_id" width="180" show-overflow-tooltip><template #default="{ row }">{{ identityText(row.principal_id) }}</template></el-table-column>
          <el-table-column prop="method" label="方法" width="90" />
          <el-table-column prop="route" label="路由" min-width="240" show-overflow-tooltip />
          <el-table-column label="状态码" width="90"><template #default="{ row }"><el-tag size="small" type="danger" effect="plain">{{ row.status_code }}</el-tag></template></el-table-column>
          <el-table-column prop="duration_ms" label="耗时 ms" width="100" align="right" />
          <el-table-column prop="level" label="level" width="90" />
        </el-table>
        <div class="mr-disabled-hint" style="margin-top: 6px">{{ logMeta(errorLogs.data.value) }}</div>
        <div class="queue-pager"><el-pagination v-model:current-page="errorPage" :page-size="logPageSize" :total="errorLogs.data.value?.total || 0" layout="total, prev, pager, next" small background @current-change="errorLogs.load()" /></div>
      </AsyncPanel>

      <el-divider content-position="left">任务阶段日志 · GET /api/parse/tasks/{task_id}/logs</el-divider>
      <el-alert v-if="taskLogs.data.value && !taskLogs.data.value.available" type="warning" :closable="false" style="margin-bottom: 10px"
        :title="`历史阶段日志不可用：${taskLogs.data.value.reason || '后端未给出原因'}`"
        description="后端只返回真实保存过的状态变化；historical_events_not_recorded 表示历史未记录，页面不回填、不补造阶段事件。" />
      <el-empty v-if="!routeTaskLogs" :image-size="54" description="运行期未加载该接口，不展示演示记录">
        <span class="mr-disabled-hint">GET /api/openapi.json 未返回 GET /api/parse/tasks/{task_id}/logs。</span>
      </el-empty>
      <el-empty v-else-if="!taskLogId.trim()" :image-size="54" description="请填写后端返回的真实 task_id 后查询" />
      <AsyncPanel v-else :state="taskLogs.state.value" :error="taskLogs.error.value" empty-text="该任务暂无已保存的阶段事件" @retry="taskLogs.load()">
        <el-table :data="taskLogs.data.value?.list || []" size="small" max-height="260">
          <el-table-column type="expand">
            <template #default="{ row }"><pre class="log-pre">{{ asJson(row.files || []) }}</pre></template>
          </el-table-column>
          <el-table-column label="时间" width="180"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
          <el-table-column prop="kind" label="事件类型" min-width="180" show-overflow-tooltip />
          <el-table-column prop="status" label="状态" width="140" />
          <el-table-column label="文件数" width="90" align="right"><template #default="{ row }">{{ (row.files || []).length }}</template></el-table-column>
        </el-table>
        <div class="mr-disabled-hint" style="margin-top: 6px">
          {{ logMeta(taskLogs.data.value) }} · 记录起始 {{ formatTime(taskLogs.data.value?.recording_started_at || '') }}
        </div>
        <div class="queue-pager"><el-pagination v-model:current-page="taskPage" :page-size="logPageSize" :total="taskLogs.data.value?.total || 0" layout="total, prev, pager, next" small background @current-change="taskLogs.load()" /></div>
      </AsyncPanel>
    </el-card>

    <el-card v-if="!v023Monitoring" shadow="never" style="margin-top: 16px">
      <template #header><div class="card-head"><span>操作审计日志</span><span class="card-sub">运行期未加载 v0.2.3 审计接口</span></div></template>
      <el-empty :image-size="54" description="无真实审计数据（运行期接口未加载）">
        <span class="mr-disabled-hint">
          当前服务的 GET /api/openapi.json 未返回 /api/system/audit-logs；不展示演示操作记录，避免把未发生的操作伪装成已留痕。
        </span>
      </el-empty>
    </el-card>

    <el-alert
      type="warning"
      :closable="false"
      style="margin-top: 16px"
      :title="releaseStatus.alertTitle"
      :description="releaseStatus.alertDescription"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAppStore } from '@/stores/app'
import { useAsyncData } from '@/composables/useAsyncData'
import { tokenStorageMode } from '@/api/client'
import { getSystemHealth } from '@/api/frontend'
import { getProcessResources, getAuditLogs } from '@/api/reviewWrite'
import { listApiLogs, listErrorLogs, getTaskLogs, loadCapabilities } from '@/api/ops'
import {
  contractState, contractMeta, contractLabel, probeContract,
  CONTRACT_ROUTES, CONTRACT_ROUTES_V023, MISSING_CAPABILITIES,
  hasV023Monitoring, hasRuntimeRoutes, hasRuntimeMethod
} from '@/api/dataSource'
import { releaseStatus } from '@/config/release'
import {
  principal, principalState, principalError, principalLoadedAt,
  loadPrincipal, principalRoleText, principalScopeText, identityText
} from '@/api/principal'
import type {
  ComponentState, HealthResponse, ProcessResources, AuditLogItem, ListResponse,
  LogQuery, OperationalLogPage, TaskLogPage
} from '@/api/types'

/**
 * v0.2.2 系统监控
 * - 组件五态来自 GET /api/system/health 真实响应，不再用静态表或旧接口探活推断
 * - 契约状态来自运行期 GET /api/openapi.json 探测，明确区分「源码已交付」与「活动实例已加载」
 * - 接口总览采用 CONTRACT_ROUTES / MISSING_CAPABILITIES 源码清单，计数不依赖已废弃的静态能力开关
 * - draft-4 运行日志（api-logs / error-logs / 任务阶段日志）按运行期方法级门控接入；
 *   未加载路由、历史未记录一律真实空态，零 DEMO 记录
 */
const store = useAppStore()
const tokenInput = ref(store.token)
const apiTab = ref('routes')
const probing = ref(false)

const identityLoading = ref(false)
async function refreshIdentity() {
  identityLoading.value = true
  try {
    await loadPrincipal(true)
  } finally {
    identityLoading.value = false
  }
}

const STATE_COLOR: Record<ComponentState, string> = {
  ONLINE: 'var(--mr-state-online)',
  OFFLINE: 'var(--mr-state-offline)',
  NOT_CONFIGURED: 'var(--mr-state-not-configured)',
  UNKNOWN: 'var(--mr-state-unknown)',
  ERROR: 'var(--mr-state-error)'
}
const VALID_STATES: ComponentState[] = ['ONLINE', 'OFFLINE', 'NOT_CONFIGURED', 'UNKNOWN', 'ERROR']
function normalizeState(value: string): ComponentState {
  return (VALID_STATES as string[]).includes(value) ? value as ComponentState : 'UNKNOWN'
}
function stateColorOf(s: ComponentState): string { return STATE_COLOR[s] }
const stateColor = computed(() => STATE_COLOR[store.apiState])
/** 服务端权限口径仅展示与收紧，不用作放宽依据；旧实例不返回时如实标注 */
const principalPermissionsText = computed(() => {
  const p = principal.value
  if (principalState.value !== 'ready' || !p) return '未确认'
  const list = p.permissions || []
  return list.length ? list.join('、') : '服务端未返回（按角色与逐请求授权判定）'
})
const principalDataScopeText = computed(() => {
  if (principalState.value !== 'ready' || !principal.value) return '未确认'
  return principal.value.data_scope || '未标注（按 scoped 处理，不代表全局范围）'
})
const stateLabel = computed(() => {
  if (store.apiState === 'ONLINE') return '真实探活成功（/api/parse/info 返回 200）；此结论不覆盖 v0.2.2 新接口'
  if (store.apiState === 'OFFLINE') return '探活失败 — 请确认 8180 服务已启动、Token 有效'
  return '尚未探测（未配置 Token 或未发起请求）'
})

const health = useAsyncData<HealthResponse>((signal) => getSystemHealth(signal))

/* v0.2.3 新增只读接口：运行期契约加载后才请求，未加载时保持空态 */
const v023Monitoring = computed(() => hasV023Monitoring())
const resources = useAsyncData<ProcessResources>(
  (signal) => getProcessResources(signal), { immediate: false }
)
const auditLogs = useAsyncData<ListResponse<AuditLogItem>>(
  (signal) => getAuditLogs({ page: 1, pageSize: 20 }, signal), { immediate: false }
)
watch(v023Monitoring, (ok) => {
  if (ok) { void resources.load(); void auditLogs.load() }
}, { immediate: true })
function runtimeHas(path: string): boolean {
  return hasRuntimeRoutes([path])
}

const CHECKABLE_ONLINE = ['fastapi', 'task_store', 'postgresql']
interface ComponentRow {
  name: string
  state: ComponentState
  check: string
  extra: string
  note: string
}
const componentRows = computed<ComponentRow[]>(() =>
  Object.entries(health.data.value?.components || {}).map(([name, c]) => {
    const flags: string[] = []
    if (c.model_ready !== undefined) flags.push(`model_ready=${c.model_ready}`)
    if (c.configured !== undefined) flags.push(`configured=${c.configured}`)
    return {
      name,
      state: normalizeState(c.state || ''),
      check: c.check || '后端未返回',
      extra: flags.join(' · '),
      note: CHECKABLE_ONLINE.includes(name)
        ? '真实只读查询成功才可为 ONLINE'
        : name === 'mineru'
          ? '仅配置检查；前端不调用云端验证'
          : '仅本地文件检查，不代表推理服务在线'
    }
  })
)

/* ───────── draft-4 运行日志：三路独立门控 / 独立分页 ───────── */
const routeApiLogs = computed(() => hasRuntimeMethod('GET', '/api/system/api-logs'))
const routeErrorLogs = computed(() => hasRuntimeMethod('GET', '/api/system/error-logs'))
const routeTaskLogs = computed(() => hasRuntimeMethod('GET', '/api/parse/tasks/{task_id}/logs'))

const logDateRange = ref<[string, string] | null>(null)
const logLevel = ref('')
const taskLogId = ref('')
const apiPage = ref(1)
const errorPage = ref(1)
const taskPage = ref(1)
const logPageSize = 20

/** 本地时间字符串 → ISO 8601 UTC（带 Z），满足后端「日期区间必须带时区」 */
function isoOf(v: string): string {
  if (!v) return ''
  const d = new Date(v)
  return Number.isNaN(d.getTime()) ? '' : d.toISOString()
}
function logQuery(page: number): LogQuery {
  const [from, to] = logDateRange.value || ['', '']
  return {
    page, pageSize: logPageSize,
    dateFrom: isoOf(from), dateTo: isoOf(to), level: logLevel.value
  }
}
const apiLogs = useAsyncData<OperationalLogPage>(
  (signal) => listApiLogs(logQuery(apiPage.value), signal), { immediate: false }
)
const errorLogs = useAsyncData<OperationalLogPage>(
  (signal) => listErrorLogs(logQuery(errorPage.value), signal), { immediate: false }
)
const taskLogs = useAsyncData<TaskLogPage>(
  (signal) => getTaskLogs(taskLogId.value.trim(), logQuery(taskPage.value), signal), { immediate: false }
)

function loadAllLogs() {
  if (routeApiLogs.value) void apiLogs.load()
  if (routeErrorLogs.value) void errorLogs.load()
  if (routeTaskLogs.value && taskLogId.value.trim()) void taskLogs.load()
}
function resetLogFilters() {
  logDateRange.value = null
  logLevel.value = ''
  taskLogId.value = ''
  apiPage.value = errorPage.value = taskPage.value = 1
  loadAllLogs()
}
/** 契约就绪 / 路由加载后再请求；未加载时不发请求，界面保持真实空态 */
watch([routeApiLogs, routeErrorLogs, routeTaskLogs, contractState], () => loadAllLogs(), { immediate: true })

function logMeta(data: OperationalLogPage | TaskLogPage | null): string {
  if (!data) return ''
  const scope = 'scope' in data ? ` · scope=${data.scope}` : ''
  return `source=${data.source}${scope} · total=${data.total} · truncated=${data.truncated} · historical_backfill=${data.historical_backfill}`
}
function asJson(v: unknown): string { return JSON.stringify(v ?? {}, null, 2) }

async function saveToken() {
  if (!tokenInput.value || tokenInput.value.length < 32) {
    ElMessage.warning('Token 长度不足 32 位，请检查后重试')
    return
  }
  await store.saveToken(tokenInput.value)
  await health.load()
  if (store.apiState === 'ONLINE' && contractState.value === 'ready') {
    ElMessage.success('Token 有效，旧解析接口与运行期契约均已就绪')
  } else if (store.apiState === 'ONLINE') {
    ElMessage.warning('Token 有效，但运行期契约探测未通过，新接口暂不可用')
  } else {
    ElMessage.warning('Token 已保存到当前会话，但未能连接后端，请确认服务已启动')
  }
}

async function reprobe() {
  probing.value = true
  try {
    await probeContract(true)
    await Promise.all([health.load(), loadPrincipal(true)])
    loadAllLogs()
    void loadCapabilities()
  } finally {
    probing.value = false
  }
}

function formatTime(v: string) { return v ? String(v).replace('T', ' ').slice(0, 19) : '—' }

onMounted(() => {
  if (store.token) void store.probeBackend()
  if (principalState.value !== 'ready') void loadPrincipal(true)
})
</script>

<style scoped>
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; gap: 12px; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); margin-left: 8px; }
.conn-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.conn-note { font-size: 13px; color: var(--mr-text-2); }
.token-form { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.log-filters { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.queue-pager { display: flex; justify-content: flex-end; margin-top: 8px; }
.log-pre { font-family: var(--mr-font); font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; margin: 0; padding: 8px; }
.security-note {
  margin-top: 12px; padding: 12px 14px; border: 1px solid #d5e5ff;
  background: #f5f9ff; border-radius: var(--mr-radius);
  font-size: 12px; color: var(--mr-text-2); line-height: 1.9;
}
.security-note b { color: #1e40af; }
.mono { font-family: monospace; font-size: 12px; }
.run-ready { color: var(--mr-state-online); font-size: 12px; }
.run-pending { color: var(--mr-state-unknown); font-size: 12px; }
@media (max-width: 1366px) {
  .security-note { line-height: 1.7; }
}
</style>
