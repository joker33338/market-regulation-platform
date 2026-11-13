<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">账号与权限管理</h1>
        <p class="page-desc">管理员账号、角色与审核范围配置（ADMIN 专属；密码不回显、审计不含密码）</p>
      </div>
      <div class="header-tags">
        <el-tag type="success" effect="plain">真实接口 /api/admin/accounts</el-tag>
        <el-tag :type="contractState === 'ready' ? 'success' : 'warning'" effect="plain">{{ contractLabel[contractState] }}</el-tag>
        <el-tag v-if="adminReady" type="danger" effect="plain">ADMIN</el-tag>
      </div>
    </div>

    <el-alert type="info" :closable="false" class="boundary-note"
      title="角色口径与安全边界（v0.2.3 draft-4）"
      :description="`ADMIN 拥有全部业务权限（all_permissions），无需额外塞入 REVIEWER；USER 仅本人数据；REVIEWER 按明确授权的 review_owner_scopes 审核写入，空列表不产生授权、不支持通配符。principal_id 是实际操作者，owner_id 是业务数据归属，两者不能互相推导；权限判定以服务端 Principal、实际方法与对象详情为准。用户名 3–64 位（字母/数字/_ . @ -），大小写不敏感且唯一；密码 12–256 字符，服务端仅保存哈希。账号列表与账号事件审计均为 ADMIN 全局范围（非当前登录者个人范围），分页 total 来自后端真实计数。当前登录身份：${identityChip}`" />

    <!-- 角色目录：GET /api/auth/roles -->
    <el-card v-if="hasRolesRoute" shadow="never">
      <template #header>
        <div class="card-head">
          <span>角色定义 <span class="real-badge">REAL</span></span>
          <span class="card-sub">GET /api/auth/roles · admin_policy={{ roles.data.value?.admin_policy || '—' }}</span>
        </div>
      </template>
      <AsyncPanel :state="roles.state.value" :error="roles.error.value" empty-text="后端未返回角色定义" @retry="roles.load()">
        <el-table :data="roles.data.value?.list || []" size="small">
          <el-table-column prop="role" label="角色" width="120" />
          <el-table-column prop="label" label="说明" min-width="160" />
          <el-table-column prop="data_scope" label="数据范围" width="140" />
          <el-table-column label="审核写入" width="100"><template #default="{ row }">{{ row.review_write ? '允许' : '禁止' }}</template></el-table-column>
          <el-table-column label="账号管理" width="100"><template #default="{ row }">{{ row.account_management ? '允许' : '禁止' }}</template></el-table-column>
        </el-table>
        <div class="mr-disabled-hint" style="margin-top: 8px">
          安全门禁：{{ (roles.data.value?.safety_gates || []).join('；') || '—' }}。修改角色 / 范围 / 状态 / 密码都会记录 before/after 审计，密码本身不入审计。
        </div>
      </AsyncPanel>
    </el-card>

    <!-- 账号列表：GET /api/admin/accounts（仅 ADMIN；非 ADMIN 403 如实呈现） -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>账号列表 <span class="real-badge">REAL</span></span>
          <div class="card-actions">
            <el-button size="small" :disabled="!adminGate || creating" @click="openCreate">创建账号</el-button>
            <el-button size="small" @click="accounts.load()">刷新</el-button>
          </div>
        </div>
      </template>
      <AsyncPanel :state="accounts.state.value" :error="accounts.error.value" :loading-text="'正在加载真实账号…'"
        empty-text="暂无账号记录（后端返回空列表，非演示数据）" @retry="accounts.load()">
        <el-table :data="accounts.data.value?.list || []" size="small" max-height="360">
          <el-table-column prop="username" label="用户名" min-width="150" show-overflow-tooltip />
          <el-table-column prop="principal_id" label="principal_id" min-width="150" show-overflow-tooltip />
          <el-table-column prop="owner_id" label="owner_id" min-width="130">
            <template #default="{ row }">{{ row.owner_id || '—（无个人 owner）' }}</template>
          </el-table-column>
          <el-table-column label="角色" width="150">
            <template #default="{ row }">
              <el-tag v-for="r in row.roles" :key="r" size="small" :type="r === 'ADMIN' ? 'danger' : r === 'REVIEWER' ? 'warning' : 'info'" effect="plain" style="margin-right: 4px">{{ r }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="审核范围" min-width="150" show-overflow-tooltip>
            <template #default="{ row }">{{ row.review_owner_scopes.length ? row.review_owner_scopes.join('、') : '—（空）' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="row.credential_status === 'active' ? 'success' : 'danger'" effect="plain">{{ row.credential_status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button text size="small" type="primary" :disabled="!adminGate" @click="openEdit(row)">修改</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="queue-pager">
          <el-pagination v-model:current-page="accountPage" :page-size="accountPageSize" :total="accounts.data.value?.total || 0"
            layout="total, prev, pager, next" small background @current-change="accounts.load()" />
        </div>
        <div class="mr-disabled-hint" style="margin-top: 8px">
          账号列表不含密码或哈希。禁用 / 撤销后旧会话下一请求即 401；重置密码后旧会话同样失效。
          最后一个有效 ADMIN 受后端保护（409），不能被误停用。
        </div>
      </AsyncPanel>
      <div v-if="!adminGate" class="mr-disabled-hint" style="margin-top: 8px">{{ adminGateHint }}</div>
    </el-card>

    <!-- 账号事件审计：GET /api/admin/account-events -->
    <el-card shadow="never" style="margin-top: 16px">
      <template #header>
        <div class="card-head">
          <span>账号变更审计 <span class="real-badge">REAL</span></span>
          <div class="card-actions">
            <el-button size="small" @click="events.load()">刷新</el-button>
          </div>
        </div>
      </template>
      <AsyncPanel :state="events.state.value" :error="events.error.value" empty-text="暂无账号变更事件（后端返回空列表）" @retry="events.load()">
        <el-table :data="events.data.value?.list || []" size="small" max-height="320">
          <el-table-column label="时间" width="170"><template #default="{ row }">{{ formatTime(row.timestamp) }}</template></el-table-column>
          <el-table-column prop="action" label="动作" width="120" show-overflow-tooltip />
          <el-table-column prop="operator_id" label="操作者" min-width="140" show-overflow-tooltip />
          <el-table-column prop="target_id" label="目标账号" min-width="140" show-overflow-tooltip />
          <el-table-column label="角色（后）" width="140">
            <template #default="{ row }">{{ (row.roles || []).join('、') || '—' }}</template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">{{ row.credential_status }}</template>
          </el-table-column>
          <el-table-column label="改密" width="70">
            <template #default="{ row }">{{ row.password_changed ? '是' : '否' }}</template>
          </el-table-column>
          <el-table-column label="before / after" min-width="220">
            <template #default="{ row }">
              <el-collapse v-if="row.before || row.after">
                <el-collapse-item title="查看变更前后（不含密码）">
                  <pre class="result-pre">{{ JSON.stringify({ before: row.before, after: row.after }, null, 2) }}</pre>
                </el-collapse-item>
              </el-collapse>
              <span v-else>—</span>
            </template>
          </el-table-column>
        </el-table>
        <div class="queue-pager">
          <el-pagination v-model:current-page="eventPage" :page-size="eventPageSize" :total="events.data.value?.total || 0"
            layout="total, prev, pager, next" small background @current-change="events.load()" />
        </div>
      </AsyncPanel>
    </el-card>

    <!-- 创建账号对话框 -->
    <el-dialog v-model="createVisible" title="创建账号（POST /api/admin/accounts）" width="560px">
      <el-form label-width="120px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" placeholder="3–64 位字母 / 数字 / _ . @ -，首位字母或数字" />
        </el-form-item>
        <el-form-item label="初始密码" required>
          <el-input v-model="form.password" type="password" show-password placeholder="12–256 个字符；提交后不回显" />
        </el-form-item>
        <el-form-item label="角色">
          <el-checkbox-group v-model="form.roles">
            <el-checkbox label="USER">USER（本人数据）</el-checkbox>
            <el-checkbox label="REVIEWER">REVIEWER（按范围审核）</el-checkbox>
            <el-checkbox label="ADMIN">ADMIN（全部业务权限）</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="owner_id">
          <el-input v-model="form.ownerId" placeholder="可选；不填由服务端生成独立 owner" />
        </el-form-item>
        <el-form-item label="审核范围">
          <el-input v-model="form.scopes" type="textarea" :rows="2"
            placeholder="可选；每行一个 owner，仅约束普通 REVIEWER；不支持通配符" />
        </el-form-item>
      </el-form>
      <div class="mr-disabled-hint">
        用户名大小写不敏感且唯一；新账号不得占用已配置独立 Token 的 principal 或普通用户 owner（409）。
        密码不写入前端任何存储；请求由后端按 ADMIN 逐次校验。
      </div>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" :disabled="!createValid" @click="submitCreate">提交创建</el-button>
      </template>
    </el-dialog>

    <!-- 修改账号对话框 -->
    <el-dialog v-model="editVisible" :title="`修改账号（PATCH /api/admin/accounts/{principal_id}）`" width="560px">
      <el-form label-width="120px">
        <el-form-item label="用户名">
          <el-input :model-value="editing?.username" disabled />
        </el-form-item>
        <el-form-item label="principal_id">
          <el-input :model-value="editing?.principal_id" disabled />
        </el-form-item>
        <el-form-item label="角色">
          <el-checkbox-group v-model="form.roles">
            <el-checkbox label="USER">USER</el-checkbox>
            <el-checkbox label="REVIEWER">REVIEWER</el-checkbox>
            <el-checkbox label="ADMIN">ADMIN</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="审核范围">
          <el-input v-model="form.scopes" type="textarea" :rows="2" placeholder="每行一个 owner；空 = 无审核写权" />
        </el-form-item>
        <el-form-item label="凭证状态">
          <el-select v-model="form.status" style="width: 200px">
            <el-option label="active（启用）" value="active" />
            <el-option label="disabled（停用）" value="disabled" />
            <el-option label="revoked（撤销）" value="revoked" />
          </el-select>
        </el-form-item>
        <el-form-item label="重置密码">
          <el-input v-model="form.password" type="password" show-password placeholder="留空 = 不修改；12–256 个字符" />
        </el-form-item>
      </el-form>
      <div class="mr-disabled-hint">
        principal_id / 用户名 / 已有 owner 不开放修改；最后一个有效 ADMIN 的停用被后端拒绝（409）。
        修改会记录 before/after 审计（密码本身不入审计）；停用或重置密码后该账号旧会话立即 401。
      </div>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="patching" @click="submitEdit">提交修改</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AsyncPanel from '@/components/AsyncPanel.vue'
import { useAsyncData } from '@/composables/useAsyncData'
import { notifyApiError, apiErrorHint } from '@/api/errors'
import { createAccount, patchAccount, listAccountEvents, listAccounts, getRoles } from '@/api/accounts'
import {
  contractState, contractLabel, hasAdminAccounts, hasRuntimeMethod, unimplementedHint
} from '@/api/dataSource'
import {
  principal, principalState, principalRoleText
} from '@/api/principal'
import { hasToken } from '@/api/client'
import type { AccountEventPage, AccountPage, AccountView, CredentialStatus, PrincipalRole, RoleCatalog } from '@/api/types'

/**
 * v0.2.3 draft-4 账号与权限管理（ADMIN 专属）
 * - 全部操作走真实接口：列表 / 创建 / PATCH / 账号事件审计，密码不回显、不落前端存储；
 * - 运行期门控：8180 正式实例（v0.2.2）未声明这些路由 → 列表不请求，按钮禁用并给出原因；
 * - 非 ADMIN 身份请求由后端返回 403，AsyncPanel 如实呈现，不做本地假数据；
 * - 提交后以真实回执为准：409（用户名冲突 / 最后管理员保护）、422（参数无效）原样提示。
 */

const accountPage = ref(1)
const accountPageSize = 20
const accounts = useAsyncData<AccountPage>(
  (signal) => listAccounts({ page: accountPage.value, pageSize: accountPageSize }, signal),
  { immediate: false }
)

const eventPage = ref(1)
const eventPageSize = 20
const events = useAsyncData<AccountEventPage>(
  (signal) => listAccountEvents({ page: eventPage.value, pageSize: eventPageSize }, signal),
  { immediate: false }
)

const hasRolesRoute = computed(() => hasRuntimeMethod('GET', '/api/auth/roles'))
const roles = useAsyncData<RoleCatalog>((signal) => getRoles(signal), { immediate: false })

/** 门控：运行期契约声明了账号路由才发起请求（8180 v0.2.2 未声明 → 保持未加载态） */
const accountsRouteReady = computed(() => hasAdminAccounts())
watch(accountsRouteReady, (ok) => {
  if (ok) {
    void accounts.load()
    void events.load()
    if (hasRolesRoute.value) void roles.load()
  }
}, { immediate: true })

/** 前端预判（收紧）：已确认身份且非 ADMIN 时禁用写按钮；最终以后端 403 为准 */
const adminReady = computed(() => principalState.value === 'ready' && !!principal.value?.roles.includes('ADMIN'))
const adminGate = computed(() => accountsRouteReady.value && (principalState.value !== 'ready' || adminReady.value))
const adminGateHint = computed(() => {
  if (!hasToken()) return '未配置会话凭证：请先在登录页登录或配置 API Token。'
  if (!accountsRouteReady.value) return unimplementedHint('GET /api/admin/accounts（v0.2.3 draft-4）')
  if (principalState.value !== 'ready') return '身份未确认：写按钮保持禁用，由后端最终判定权限。'
  if (!adminReady.value) return `当前身份 ${principal.value?.principal_id}（${principalRoleText.value}）不含 ADMIN：账号管理写操作保持禁用。`
  return ''
})

const identityChip = computed(() => {
  if (principalState.value === 'ready' && principal.value) {
    return `${principal.value.principal_id}（${principalRoleText.value}）`
  }
  return principalState.value === 'ready' ? '未确认' : '身份未确认'
})

/* ───────── 创建 / 修改表单 ───────── */
const createVisible = ref(false)
const editVisible = ref(false)
const creating = ref(false)
const patching = ref(false)
const editing = ref<AccountView | null>(null)

const form = reactive({
  username: '',
  password: '',
  roles: [] as PrincipalRole[],
  ownerId: '',
  scopes: '',
  status: 'active' as CredentialStatus
})

const createValid = computed(() =>
  form.username.trim().length >= 3 && form.password.length >= 12 && form.password.length <= 256
)

function openCreate() {
  form.username = ''
  form.password = ''
  form.roles = ['USER']
  form.ownerId = ''
  form.scopes = ''
  createVisible.value = true
}

function parseScopes(value: string): string[] {
  return value.split(/[\n,，;；\s]+/).map((s) => s.trim()).filter(Boolean)
}

async function submitCreate() {
  if (!createValid.value || creating.value) return
  creating.value = true
  try {
    const created = await createAccount({
      username: form.username.trim(),
      password: form.password,
      roles: form.roles,
      owner_id: form.ownerId.trim() || null,
      review_owner_scopes: parseScopes(form.scopes)
    })
    form.password = ''
    createVisible.value = false
    ElMessage.success(`账号已创建：${created.username}（principal_id 由服务端生成）`)
    void accounts.load()
    void events.load()
  } catch (err) {
    form.password = ''
    notifyApiError(err, '创建账号失败')
  } finally {
    creating.value = false
  }
}

function openEdit(row: AccountView) {
  editing.value = row
  form.username = row.username
  form.password = ''
  form.roles = [...row.roles]
  form.ownerId = row.owner_id || ''
  form.scopes = row.review_owner_scopes.join('\n')
  form.status = row.credential_status
  editVisible.value = true
}

async function submitEdit() {
  const target = editing.value
  if (!target || patching.value) return
  patching.value = true
  try {
    const body: Parameters<typeof patchAccount>[1] = {
      roles: [...form.roles],
      review_owner_scopes: parseScopes(form.scopes),
      credential_status: form.status
    }
    if (form.password) {
      if (form.password.length < 12 || form.password.length > 256) {
        ElMessage.warning('重置密码需 12–256 个字符')
        patching.value = false
        return
      }
      body.password = form.password
    }
    const updated = await patchAccount(target.principal_id, body)
    form.password = ''
    editVisible.value = false
    ElMessage.success(`已提交修改：${updated.username}（状态 ${updated.credential_status}）`)
    void accounts.load()
    void events.load()
  } catch (err) {
    form.password = ''
    const hint = apiErrorHint(err)
    if (hint.includes('409')) {
      ElMessage.error(`修改被拒绝（409）：可能是最后一个有效管理员保护或范围冲突；${hint}`)
    } else {
      notifyApiError(err, '修改账号失败')
    }
  } finally {
    patching.value = false
  }
}

function formatTime(v: string) {
  return v ? String(v).replace('T', ' ').slice(0, 19) : '—'
}
</script>

<style scoped>
.header-tags { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.boundary-note { margin-bottom: 12px; }
.card-head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; gap: 12px; flex-wrap: wrap; }
.card-actions { display: flex; gap: 8px; }
.card-sub { font-weight: 400; font-size: 12px; color: var(--mr-text-3); }
.queue-pager { display: flex; justify-content: flex-end; margin-top: 10px; }
.result-pre { font-family: var(--mr-font); font-size: 12px; line-height: 1.7; white-space: pre-wrap; word-break: break-word; margin: 0; }
</style>
