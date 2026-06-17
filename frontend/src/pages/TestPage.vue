<script setup>
import { ref, onMounted, onUnmounted, computed } from "vue"
import { getTask, listTasks, deleteTask } from "../api.js"
import DocGenerator from "../components/DocGenerator.vue"
import DocPreview from "../components/DocPreview.vue"

const tasks    = ref([])
const view     = ref("home")
const activeId = ref(null)
const active   = ref(null)
let timer = null

const STATUS = {
  pending:   { label: "排队", dot: "#f59e0b" },
  running:   { label: "生成", dot: "#3b82f6" },
  completed: { label: "完成", dot: "#10b981" },
  failed:    { label: "失败", dot: "#ef4444" },
}

const count      = computed(() => tasks.value.length)
const isDesktop  = computed(() => view.value === "home" || view.value === "detail")

async function fetchTasks() {
  try {
    const r = await listTasks(1, 100)
    tasks.value = (r.data.items || []).filter(t => t.doc_type === "测试用例")
  } catch (_) {}
}
async function selectTask(id) {
  activeId.value = id; view.value = "detail"; await refresh()
}
async function refresh() {
  if (!activeId.value) return
  try {
    const r = await getTask(activeId.value); active.value = r.data
    if (r.data.status === "running" || r.data.status === "pending") startPoll()
    else { stopPoll(); fetchTasks() }
  } catch (_) {}
}
function startPoll() { stopPoll(); timer = setInterval(refresh, 3000) }
function stopPoll()  { if (timer) { clearInterval(timer); timer = null } }

function goHome()   { view.value = "home";   activeId.value = null; active.value = null; stopPoll() }
function goCreate() { view.value = "create"; activeId.value = null; active.value = null; stopPoll() }

async function onCreated(taskId) {
  activeId.value = taskId
  active.value   = { id: taskId, status: "pending", doc_type: "测试用例" }
  view.value     = "detail"
  startPoll(); fetchTasks()
}
async function onDelete(taskId) {
  try { await deleteTask(taskId); goHome(); fetchTasks() } catch (_) {}
}

onMounted(fetchTasks)
onUnmounted(stopPoll)

function fmt(t) {
  if (!t) return ""
  const d = new Date(t)
  const p = n => String(n).padStart(2,"0")
  return `${d.getMonth()+1}/${d.getDate()} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<template>
  <!-- ================ 桌面 ================ -->
  <div class="d-shell">
    <!-- 左栏 -->
    <aside class="d-side">
      <div class="d-side-head">
        <div class="d-side-brand">
          <span class="d-side-logo">&#x1F9EA;</span>
          <span class="d-side-title">Test-Agent</span>
        </div>
        <button class="d-new-btn" @click="goCreate">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          新建
        </button>
      </div>

      <div class="d-divider"></div>

      <div class="d-list">
        <div
          v-for="t in tasks" :key="t.id"
          :class="['d-row', { 'd-row--on': t.id === activeId }]"
          @click="selectTask(t.id)"
        >
          <span class="d-dot" :style="{ background: STATUS[t.status]?.dot }"></span>
          <div class="d-info">
            <span class="d-name">{{ t.custom_name || t.doc_type || '未命名' }}</span>
            <span class="d-doc-type">{{ t.doc_type }}</span>
          </div>
          <span class="d-badge" :style="{ color: STATUS[t.status]?.dot }">
            {{ STATUS[t.status]?.label }}
          </span>
        </div>

        <div v-if="count === 0" class="d-empty">
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none"><rect x="6" y="8" width="28" height="24" rx="4" stroke="#cbd5e1" stroke-width="1.5"/><line x1="13" y1="17" x2="27" y2="17" stroke="#e2e8f0" stroke-width="2" stroke-linecap="round"/><line x1="13" y1="22" x2="23" y2="22" stroke="#e2e8f0" stroke-width="2" stroke-linecap="round"/></svg>
          <span>暂无测试任务</span>
        </div>
      </div>

      <div class="d-foot">{{ count }} 个测试任务</div>
    </aside>

    <!-- 右栏 -->
    <main class="d-main">
      <div v-if="view === 'home'" class="d-welcome">
        <div class="d-welcome-icon">
          <svg width="56" height="56" viewBox="0 0 56 56" fill="none"><rect x="8" y="12" width="40" height="32" rx="5" stroke="#cbd5e1" stroke-width="2"/><path d="M20 4v6M36 4v6M8 22h40" stroke="#cbd5e1" stroke-width="2" stroke-linecap="round"/><line x1="18" y1="30" x2="38" y2="30" stroke="#e2e8f0" stroke-width="3" stroke-linecap="round"/><line x1="18" y1="36" x2="32" y2="36" stroke="#e2e8f0" stroke-width="3" stroke-linecap="round"/></svg>
        </div>
        <h2>生成测试用例</h2>
        <p>从左侧列表选择测试任务查看详情，或点击「新建」粘贴需求文档+设计文档，AI 自动生成全覆盖测试用例</p>
      </div>
      <DocGenerator v-if="view === 'create'" @task-created="onCreated" :allowed-types='["测试用例"]' />
      <DocPreview
        v-if="view === 'detail' && active"
        :task="active"
        @back="goHome"
        @delete="onDelete"
      />
    </main>
  </div>

  <!-- ================ 手机 ================ -->
  <div class="m-shell">
    <div class="m-bar">
      <span class="m-bar-logo">&#x1F9EA;</span>
      <span class="m-bar-title">Test-Agent</span>
      <button v-if="view === 'detail'" class="m-bar-btn" @click="goHome">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
      </button>
      <button v-if="view === 'home'" class="m-bar-btn" @click="goCreate">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      </button>
      <div v-if="view === 'create'" class="m-bar-spacer"></div>
    </div>

    <div class="m-body">
      <div v-if="view === 'home'">
        <div class="m-list">
          <div
            v-for="t in tasks" :key="t.id"
            class="m-card"
            @click="selectTask(t.id)"
          >
            <div class="m-card-top">
              <span class="m-card-name">{{ t.custom_name || t.doc_type || '未命名' }}</span>
              <span class="m-card-badge" :style="{ color: STATUS[t.status]?.dot }">
                {{ STATUS[t.status]?.label }}
              </span>
            </div>
            <div class="m-card-bot">
              <span class="m-card-type">{{ t.doc_type }}</span>
              <span>{{ fmt(t.created_at) }}</span>
            </div>
          </div>

          <div v-if="count === 0" class="m-empty">
            <p>欢迎使用 Test-Agent</p>
            <span>点击右上角 + 创建测试用例生成任务</span>
          </div>
        </div>
      </div>

      <DocGenerator v-if="view === 'create'" @task-created="onCreated" :allowed-types='["测试用例"]' />
      <DocPreview
        v-if="view === 'detail' && active"
        :task="active"
        @back="goHome"
        @delete="onDelete"
      />
    </div>
  </div>
</template>

<style scoped>
/* ================================================================
   桌面双栏
   ================================================================ */
.d-shell { display:flex; height:100%; min-width:960px }

/* 左栏 */
.d-side {
  width:340px; min-width:340px; background:var(--surface);
  display:flex; flex-direction:column;
  border-right:1px solid var(--border);
}
.d-side-head {
  display:flex; align-items:center; justify-content:space-between;
  padding:18px 18px 14px;
}
.d-side-brand { display:flex; align-items:center; gap:8px }
.d-side-logo  { font-size:22px }
.d-side-title { font-size:16px; font-weight:700; letter-spacing:-0.3px }
.d-new-btn {
  display:inline-flex; align-items:center; gap:5px;
  padding:7px 14px; background:var(--primary); color:#fff;
  border:none; border-radius:8px; font-size:13px; font-weight:600;
  cursor:pointer; transition:background .12s;
}
.d-new-btn:hover { background:#4338ca }

.d-divider { height:1px; background:var(--border); margin:0 18px }

.d-list { flex:1; overflow-y:auto; padding:6px 10px }

.d-row {
  display:flex; align-items:center; gap:10px;
  padding:10px 12px; border-radius:var(--radius);
  cursor:pointer; min-height:48px;
  transition:background .12s;
}
.d-row:hover         { background:#f8fafc }
.d-row--on           { background:#eef2ff }
.d-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0 }
.d-info { display:flex; flex-direction:column; min-width:0; flex:1 }
.d-name { font-size:13px; font-weight:500; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.d-time { font-size:11px; color:var(--text-muted); margin-top:1px }
.d-doc-type { font-size:11px; color:var(--text-muted); margin-top:1px }
.d-badge{ font-size:11px; font-weight:600; flex-shrink:0 }

.d-empty {
  display:flex; flex-direction:column; align-items:center; gap:8px;
  padding:40px 16px; color:var(--text-muted); font-size:13px;
}
.d-foot { padding:10px 18px; border-top:1px solid var(--border); font-size:12px; color:var(--text-muted) }

/* 右栏 */
.d-main { flex:1; overflow-y:auto; background:var(--bg) }

.d-welcome {
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  height:100%; text-align:center; padding:40px;
}
.d-welcome-icon { margin-bottom:20px; opacity:.6 }
.d-welcome h2 { font-size:20px; font-weight:700; margin-bottom:8px }
.d-welcome p  { font-size:14px; color:var(--text-muted); max-width:300px; line-height:1.6 }

/* ================================================================
   手机
   ================================================================ */
.m-shell { display:none; flex-direction:column; height:100% }

.m-bar {
  display:flex; align-items:center; gap:8px; flex-shrink:0;
  padding:8px 12px; padding-top:calc(8px + var(--safe-top));
  background:var(--surface); border-bottom:1px solid var(--border);
}
.m-bar-logo  { font-size:20px }
.m-bar-title { flex:1; font-size:16px; font-weight:700 }
.m-bar-btn {
  background:none; border:none; cursor:pointer; color:var(--text-soft);
  min-width:40px; min-height:40px;
  display:flex; align-items:center; justify-content:center;
  border-radius:8px;
}
.m-bar-btn:active { background:#f1f5f9 }
.m-bar-spacer { width:40px }

.m-body { flex:1; overflow-y:auto }

/* 手机任务列表 */
.m-list { padding:12px }

.m-card {
  background:var(--surface); border-radius:12px; padding:16px;
  margin-bottom:10px; cursor:pointer;
  border-left:3px solid var(--dot);
  box-shadow:0 1px 2px rgba(0,0,0,.03);
  transition:box-shadow .15s;
}
.m-card:active { box-shadow:0 2px 8px rgba(0,0,0,.06) }

.m-card-top { display:flex; align-items:center; gap:8px; margin-bottom:10px; color:var(--text-soft) }
.m-card-name { font-size:14px; font-weight:600; flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.m-card-badge{ font-size:12px; font-weight:600; flex-shrink:0 }

.m-card-type { font-size:12px; color:var(--text-muted) }
.m-card-bot { display:flex; justify-content:space-between; font-size:12px; color:var(--text-muted); padding-left:24px }

.m-empty { display:flex; flex-direction:column; align-items:center; gap:8px; padding:60px 20px; color:var(--text-muted) }
.m-empty p  { font-size:16px; font-weight:600; color:var(--text-soft) }
.m-empty span{ font-size:13px }

/* ================================================================
   响应式
   ================================================================ */
@media (max-width:959px) {
  .d-shell { display:none }
  .m-shell { display:flex }
}
</style>
