<script setup>
import { ref, computed } from "vue"
import { createTask, browseFolder } from "../api.js"

const emit = defineEmits(["task-created"])

const docType     = ref("需求规格说明书")
const material    = ref("")
const projectPath = ref("")
const customName  = ref("")
const loading     = ref(false)
const error       = ref("")
const browsing    = ref(false)
const docTypes    = ["需求规格说明书", "软件设计文档"]

const isDesignDoc = computed(() => docType.value === "软件设计文档")

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
  if (!isDesignDoc.value) {
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
        <h1>新建文档生成任务</h1>
        <p v-if="!isDesignDoc">粘贴项目素材，AI 自动生成需求规格说明书</p>
        <p v-else>选择项目文件夹自动扫描代码，AI 生成软件设计文档</p>
      </div>
    </div>

    <div class="cols">
      <div class="col-form">
        <div class="field">
          <label>文档类型</label>
          <div class="select-wrap">
            <select v-model="docType">
              <option v-for="t in docTypes" :key="t" :value="t">{{ t }}</option>
            </select>
            <svg class="chevron" width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </div>
        </div>

        <div class="field">
          <label>文档名称（可选，默认使用文档类型名）</label>
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

        <div class="field field--grow">
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
          <h3 v-if="!isDesignDoc">写作提示</h3>
          <h3 v-else>设计文档提示</h3>
          <ul v-if="!isDesignDoc">
            <li>粘贴项目的背景介绍、核心需求、功能列表</li>
            <li>包含技术栈、约束条件可提升生成质量</li>
            <li>素材越详细，生成的文档越完整</li>
          </ul>
          <ul v-else>
            <li>点击"浏览"选择项目文件夹，自动扫描源代码</li>
            <li>支持 Python/Java/Go/Vue/React 等常见项目</li>
            <li>补充说明可添加特殊设计约束或要求</li>
          </ul>
        </div>
        <div class="tip-card">
          <h3>输出说明</h3>
          <ul v-if="!isDesignDoc">
            <li>生成标准需求规格说明书（SRS）</li>
            <li>支持 Markdown 格式，可下载 .md 文件</li>
            <li>生成时间约 1-2 分钟</li>
          </ul>
          <ul v-else>
            <li>生成标准软件设计文档（架构、接口、数据设计）</li>
            <li>包含 Mermaid 架构图、流程图、ER 图</li>
            <li>含代码扫描，生成时间约 2-3 分钟</li>
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

.err {
  margin-top: 16px; padding: 14px 16px;
  background: #fef2f2; color: #dc2626; border-radius: 10px;
  font-size: 13px; display: flex; align-items: flex-start; gap: 8px;
  border: 1px solid #fecaca;
}
.fade-enter-active, .fade-leave-active { transition: opacity .2s }
.fade-enter-from, .fade-leave-to { opacity: 0 }

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
