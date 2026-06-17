<script setup>
import { ref, computed, watch } from "vue"
import { createTask, browseFolder, listTasks, getTask } from "../api.js"

const props = defineProps({
  allowedTypes: { type: Array, default: () => ["需求规格说明书", "软件设计文档", "测试用例"] },
})
const emit = defineEmits(["task-created"])

const docType     = ref(props.allowedTypes[0] || "需求规格说明书")
const material    = ref("")
const projectPath = ref("")
const customName  = ref("")
const loading     = ref(false)
const error       = ref("")
const browsing    = ref(false)
const availableTypes = computed(() => props.allowedTypes)

const isDesignDoc = computed(() => docType.value === "软件设计文档")
const isTestCase   = computed(() => docType.value === "测试用例")
const isSingleType = computed(() => availableTypes.value.length === 1)

// 已完成任务列表（测试用例模式用）
const completedTasks = ref([])
const selectedTasks  = ref([])
const fetchingTasks  = ref(false)

watch(docType, (val) => {
  if (val === "测试用例") {
    fetchCompletedTasks()
  }
}, { immediate: true })

watch(() => props.allowedTypes, (types) => {
  if (types && types.length > 0 && !types.includes(docType.value)) {
    docType.value = types[0]
  }
})

async function fetchCompletedTasks() {
  fetchingTasks.value = true
  try {
    const r = await listTasks(1, 50)
    completedTasks.value = (r.data.items || []).filter(
      t => t.status === "completed" && t.doc_type !== "测试用例"
    )
  } catch (e) {
    // ignore
  } finally {
    fetchingTasks.value = false
  }
}

function toggleTask(taskId) {
  const idx = selectedTasks.value.indexOf(taskId)
  if (idx >= 0) {
    selectedTasks.value.splice(idx, 1)
  } else {
    selectedTasks.value.push(taskId)
  }
}

async function openFolderDialog() {
  browsing.value = true
  try {
    const r = await browseFolder()
    if (r.data.path) {
      projectPath.value = r.data.path
    }
  } catch (e) {
    if (e.response?.status !== 400) {
      error.value = e.response?.data?.detail || "打开文件夹失败"
    }
  } finally {
    browsing.value = false
  }
}

async function submit() {
  if (isTestCase.value) {
    // 从选中任务合并素材，或使用手动粘贴的素材
    if (selectedTasks.value.length > 0) {
      loading.value = true; error.value = ""
      try {
        let combined = ""
        for (const tid of selectedTasks.value) {
          const r = await getTask(tid)
          combined += `===== ${r.data.doc_type} =====\n${r.data.result_md || ""}\n\n`
        }
        material.value = combined
      } catch (e) {
        error.value = "获取任务内容失败"
        loading.value = false; return
      }
    }
    if (!material.value.trim()) {
      error.value = "请选择已生成的文档或手动粘贴素材"; loading.value = false; return
    }
  } else if (!isDesignDoc.value) {
    if (!material.value.trim()) { error.value = "请输入素材内容"; return }
  } else {
    if (!projectPath.value.trim() && !material.value.trim()) {
      error.value = "请选择项目路径或输入素材内容"; return
    }
  }
  error.value = ""; loading.value = true
  try {
    const r = await createTask(
      material.value.trim(),
      docType.value,
      projectPath.value.trim() || null,
      customName.value.trim(),
    )
    emit("task-created", r.data.id)
    material.value = ""
    projectPath.value = ""
    customName.value = ""
    selectedTasks.value = []
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || "提交失败"
  } finally { loading.value = false }
}
</script>

<template>
  <div class="create">
    <div class="hero">
      <div class="hero-icon">
        <svg width="36" height="36" viewBox="0 0 36 36" fill="none"><rect x="5" y="7" width="26" height="22" rx="4" stroke="#4f46e5" stroke-width="2"/><line x1="11" y1="15" x2="25" y2="15" stroke="#c7d2fe" stroke-width="2" stroke-linecap="round"/><line x1="11" y1="20" x2="21" y2="20" stroke="#c7d2fe" stroke-width="2" stroke-linecap="round"/></svg>
      </div>
      <div>
        <h1>{{ isSingleType ? '新建' + availableTypes[0] + '任务' : '新建文档生成任务' }}</h1>
        <p v-if="isDesignDoc">选择项目文件夹自动扫描代码，AI 生成软件设计文档</p>
        <p v-else-if="isTestCase">粘贴需求文档+设计文档，AI 自动生成白盒测试用例（覆盖全路径）</p>
        <p v-else>粘贴项目素材，AI 自动生成需求规格说明书</p>
      </div>
    </div>

    <div class="cols">
      <div class="col-form">
        <div class="field">
          <label>{{ isSingleType ? '任务类型' : '文档类型' }}</label>
          <div v-if="isSingleType" class="type-static">{{ availableTypes[0] }}</div>
          <div v-else class="select-wrap">
            <select v-model="docType">
              <option v-for="t in availableTypes" :key="t" :value="t">{{ t }}</option>
            </select>
            <svg class="chevron" width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
        </div>

        <div class="field">
          <label>{{ isSingleType ? '任务名称（可选）' : '文档名称（可选，默认使用文档类型名）' }}</label>
          <input
            v-model="customName"
            type="text"
            :placeholder="'如：XX系统 ' + docType"
            class="name-input"
          />
        </div>

        <div v-if="isDesignDoc" class="field">
          <label>项目路径</label>
          <div class="path-row">
            <input
              v-model="projectPath"
              type="text"
              placeholder="输入路径或点击浏览选择文件夹"
              class="path-input"
            />
            <button class="browse-btn" :disabled="browsing" @click="openFolderDialog">
              <span v-if="browsing" class="spin-small"></span>
              <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/></svg>
              {{ browsing ? "..." : "浏览" }}
            </button>
          </div>
        </div>

        <div v-if="!isTestCase" class="field field--grow">
          <label class="label-row">
            <span>{{ isDesignDoc ? "补充说明（可选）" : "素材内容" }}</span>
            <span v-if="!isDesignDoc" class="hint">{{ material.length }} 字</span>
          </label>
          <textarea
            v-model="material"
            :placeholder="isDesignDoc
              ? '项目的补充说明、特殊设计要求…'
              : '在此粘贴项目素材文本…'"
          ></textarea>
        </div>
        <div v-else class="field field--grow">
          <label>从已生成文档中选择（可选）</label>
          <div v-if="completedTasks.length === 0 && !fetchingTasks" class="hint-text">
            暂无已完成的文档，请先生成需求文档或设计文档，或直接粘贴素材
          </div>
          <div v-if="fetchingTasks" class="hint-text">加载中…</div>
          <div v-if="completedTasks.length > 0" class="task-pick-list">
            <label v-for="t in completedTasks" :key="t.id" class="task-pick-item"
                   :class="{ checked: selectedTasks.includes(t.id) }">
              <input type="checkbox" :checked="selectedTasks.includes(t.id)"
                     @change="toggleTask(t.id)" />
              <span class="task-pick-type">{{ t.doc_type }}</span>
              <span class="task-pick-name">{{ t.custom_name || t.id }}</span>
            </label>
          </div>
          <label class="label-row" style="margin-top:12px">
            <span>或手动粘贴素材</span>
            <span class="hint">{{ material.length }} 字</span>
          </label>
          <textarea
            v-model="material"
            placeholder="粘贴需求文档和设计文档内容…"
            style="min-height:120px"
          ></textarea>
        </div>

        <button class="btn" :disabled="loading" @click="submit">
          <span v-if="loading" class="spin"></span>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          {{ loading ? "提交中..." : "开始生成" }}
        </button>

        <Transition name="fade">
          <div v-if="error" class="err">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            {{ error }}
          </div>
        </Transition>
      </div>

      <div class="col-tips">
        <div class="tip-card">
          <h3 v-if="isDesignDoc">设计文档提示</h3>
          <h3 v-else-if="isTestCase">测试用例提示</h3>
          <h3 v-else>写作提示</h3>
          <ul v-if="isDesignDoc">
            <li>点击"浏览"选择项目文件夹，自动扫描源代码</li>
            <li>支持 Python/Java/Go/Vue/React 等常见项目</li>
            <li>补充说明可添加特殊设计约束或要求</li>
          </ul>
          <ul v-else-if="isTestCase">
            <li>先在左侧生成需求文档和设计文档</li>
            <li>将两份文档内容粘贴到素材输入框</li>
            <li>AI 根据文档生成覆盖全路径的白盒测试用例</li>
          </ul>
          <ul v-else>
            <li>粘贴项目的背景介绍、核心需求、功能列表</li>
            <li>包含技术栈、约束条件可提升生成质量</li>
            <li>素材越详细，生成的文档越完整</li>
          </ul>
        </div>
        <div class="tip-card">
          <h3>输出说明</h3>
          <ul v-if="isDesignDoc">
            <li>生成标准软件设计文档（架构、接口、数据设计）</li>
            <li>包含 Mermaid 架构图、流程图、ER 图</li>
            <li>含代码扫描，生成时间约 2-3 分钟</li>
          </ul>
          <ul v-else-if="isTestCase">
            <li>生成 DRG 入组测试用例文档</li>
            <li>含自然语言病历 + 编码映射 + 预期分组路径</li>
            <li>包含 Mermaid 分组路径覆盖图</li>
            <li>生成时间约 1-2 分钟</li>
          </ul>
          <ul v-else>
            <li>生成标准需求规格说明书（SRS）</li>
            <li>支持 Markdown 格式，可下载 .md 文件</li>
            <li>生成时间约 1-2 分钟</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.create { padding: 32px; height: 100%; display: flex; flex-direction: column }

.hero { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 32px }
.hero-icon { flex-shrink: 0; margin-top: 2px }
.hero h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; color: var(--text, #0f172a) }
.hero p  { font-size: 14px; color: var(--text-muted, #94a3b8) }

.cols { display: flex; gap: 28px; flex: 1; min-height: 0 }
.col-form { flex: 1; display: flex; flex-direction: column; min-width: 0 }
.col-tips { width: 240px; flex-shrink: 0; display: flex; flex-direction: column; gap: 16px }

.field { margin-bottom: 22px }
.field--grow { flex: 1; display: flex; flex-direction: column; min-height: 0 }
label { display: block; margin-bottom: 6px; font-size: 13px; font-weight: 600; color: var(--text-soft, #475569) }
.label-row { display: flex; justify-content: space-between }
.hint { font-weight: 400; font-size: 12px; color: var(--text-muted, #94a3b8) }

.select-wrap { position: relative }
select {
  width: 100%; padding: 13px 42px 13px 16px;
  border: 1.5px solid var(--border, #e2e8f0); border-radius: 10px;
  font-size: 15px; font-family: inherit; color: var(--text, #0f172a);
  background: #f8fafc; appearance: none; cursor: pointer; min-height: 50px;
  transition: border-color .15s, box-shadow .15s;
}
select:focus { outline: none; border-color: var(--primary, #4f46e5); box-shadow: 0 0 0 3px rgba(79,70,229,.08); background: #fff }
.chevron { position: absolute; right: 14px; top: 50%; transform: translateY(-50%); pointer-events: none }

.path-row { display: flex; gap: 10px }
.path-input {
  flex: 1; padding: 13px 16px;
  border: 1.5px solid var(--border, #e2e8f0); border-radius: 10px;
  font-size: 15px; font-family: monospace; color: var(--text, #0f172a);
  background: #f8fafc; min-height: 50px;
  transition: border-color .15s, box-shadow .15s;
}
.path-input:focus { outline: none; border-color: var(--primary, #4f46e5); box-shadow: 0 0 0 3px rgba(79,70,229,.08); background: #fff }
.path-input::placeholder { color: #cbd5e1; font-family: inherit }

.type-static {
  padding: 13px 16px; font-size: 14px; font-weight: 500;
  color: var(--text, #0f172a); background: #f8fafc;
  border: 1px solid var(--border, #e2e8f0); border-radius: 10px;
}
.name-input {
  width: 100%; padding: 13px 16px;
  border: 1.5px solid var(--border, #e2e8f0); border-radius: 10px;
  font-size: 15px; font-family: inherit; color: var(--text, #0f172a);
  background: #f8fafc; min-height: 50px;
  transition: border-color .15s, box-shadow .15s;
}
.name-input:focus { outline: none; border-color: var(--primary, #4f46e5); box-shadow: 0 0 0 3px rgba(79,70,229,.08); background: #fff }
.name-input::placeholder { color: #cbd5e1 }

.browse-btn {
  flex-shrink: 0; padding: 0 18px;
  border: 1.5px solid var(--primary, #4f46e5); border-radius: 10px;
  font-size: 14px; font-weight: 600; font-family: inherit;
  color: var(--primary, #4f46e5); background: #fff;
  cursor: pointer; display: flex; align-items: center; gap: 6px;
  transition: background .15s, color .15s;
}
.browse-btn:hover:not(:disabled) { background: #4f46e5; color: #fff }
.browse-btn:disabled { opacity: .6; cursor: not-allowed }

.spin-small {
  width: 14px; height: 14px; border: 2px solid #c7d2fe;
  border-top-color: #4f46e5; border-radius: 50%; animation: rotate .6s linear infinite;
}

textarea {
  width: 100%; padding: 16px; flex: 1; min-height: 280px;
  border: 1.5px solid var(--border, #e2e8f0); border-radius: 10px;
  font-size: 15px; font-family: inherit; line-height: 1.75; color: var(--text, #0f172a);
  background: #f8fafc; resize: none;
  transition: border-color .15s, box-shadow .15s;
}
textarea:focus { outline: none; border-color: var(--primary, #4f46e5); box-shadow: 0 0 0 3px rgba(79,70,229,.08); background: #fff }
textarea::placeholder { color: #cbd5e1 }

.btn {
  padding: 15px; margin-top: 20px;
  background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff;
  border: none; border-radius: 12px; font-size: 16px; font-weight: 700;
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  gap: 8px; min-height: 54px;
  box-shadow: 0 4px 14px rgba(79,70,229,.3);
  transition: transform .1s, box-shadow .15s, filter .15s;
}
.btn:hover:not(:disabled) { filter: brightness(1.05); box-shadow: 0 6px 20px rgba(79,70,229,.35) }
.btn:active:not(:disabled) { transform: scale(.98) }
.btn:disabled { opacity: .5; cursor: not-allowed; filter: none }

.spin {
  width: 20px; height: 20px; border: 2.5px solid rgba(255,255,255,.3);
  border-top-color: #fff; border-radius: 50%; animation: rotate .6s linear infinite;
}
@keyframes rotate { to { transform: rotate(360deg) } }

.builtin-note {
  display: flex; gap: 12px; padding: 16px;
  background: #eef2ff; border: 1px solid #c7d2fe;
  border-radius: 10px; align-items: flex-start;
  flex: 1; min-height: 100px;
}
.builtin-note svg { flex-shrink: 0; margin-top: 2px }
.builtin-note strong { font-size: 14px; color: #4338ca }
.builtin-note p { font-size: 13px; color: #6366f1; margin-top: 4px; line-height: 1.6 }

.err {
  margin-top: 16px; padding: 14px 16px;
  background: #fef2f2; color: #dc2626; border-radius: 10px;
  font-size: 13px; display: flex; align-items: flex-start; gap: 8px;
  border: 1px solid #fecaca;
}
.fade-enter-active, .fade-leave-active { transition: opacity .2s }
.fade-enter-from, .fade-leave-to { opacity: 0 }

.hint-text {
  font-size: 13px; color: var(--text-muted, #94a3b8); padding: 8px 0;
}
.task-pick-list {
  max-height: 160px; overflow-y: auto;
  border: 1px solid var(--border, #e2e8f0); border-radius: 8px;
}
.task-pick-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; cursor: pointer; font-size: 13px;
  border-bottom: 1px solid #f1f5f9;
}
.task-pick-item:last-child { border-bottom: none }
.task-pick-item.checked { background: #eef2ff }
.task-pick-item input { margin: 0 }
.task-pick-type {
  flex-shrink: 0; padding: 2px 6px;
  background: #e2e8f0; border-radius: 4px; font-size: 11px; color: #475569;
}
.task-pick-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--text, #0f172a);
}

.tip-card {
  background: #f8fafc; border: 1px solid var(--border, #e2e8f0);
  border-radius: 12px; padding: 20px;
}
.tip-card h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--text-soft, #475569) }
.tip-card ul { padding-left: 18px }
.tip-card li { font-size: 13px; color: var(--text-muted, #94a3b8); margin-bottom: 8px; line-height: 1.6 }
.tip-card li:last-child { margin-bottom: 0 }

/* ================================================================
   手机端
   ================================================================ */
@media (max-width: 959px) {
  .create {
    padding: 0;
    height: 100%;
    background: var(--surface, #fff);
  }

  .hero {
    margin: 0; flex-shrink: 0;
    padding: 24px 20px 0;
    gap: 12px;
  }
  .hero-icon {
    width: 42px; height: 42px; flex-shrink: 0;
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 12px rgba(79,70,229,.25);
  }
  .hero-icon :deep(svg) { display: none }
  .hero-icon::before { content: "\270F\FE0F"; font-size: 20px }
  .hero h1 { font-size: 20px; font-weight: 700 }
  .hero p  { font-size: 13px; color: var(--text-muted, #94a3b8); margin-top: 2px }

  .cols {
    flex-direction: column;
    gap: 0; margin: 0; padding: 0;
    background: none; border-radius: 0; box-shadow: none;
  }
  .col-tips { display: none }

  .col-form {
    padding: 20px 20px 24px;
  }

  .field { margin-bottom: 0 }
  .field:first-child { margin-bottom: 16px }

  label { font-size: 14px; margin-bottom: 8px }

  select {
    padding: 13px 42px 13px 16px; font-size: 15px;
    min-height: 50px; border-radius: 10px;
    background: #f8fafc;
  }

  .type-static {
  padding: 13px 16px; font-size: 14px; font-weight: 500;
  color: var(--text, #0f172a); background: #f8fafc;
  border: 1px solid var(--border, #e2e8f0); border-radius: 10px;
}
.name-input {
    padding: 13px 16px; font-size: 14px;
    min-height: 50px; border-radius: 10px;
    background: #f8fafc;
    margin-bottom: 16px;
  }

  .path-row { flex-direction: column }
  .path-input {
    padding: 13px 16px; font-size: 14px;
    min-height: 50px; border-radius: 10px;
    background: #f8fafc;
    margin-bottom: 0;
  }
  .browse-btn {
    justify-content: center; min-height: 46px;
    border-radius: 10px;
  }

  textarea {
    min-height: 160px;
  }

  .btn {
    margin-top: 16px; border-radius: 12px;
    min-height: 52px; font-size: 16px;
    flex-shrink: 0;
  }
}
</style>
