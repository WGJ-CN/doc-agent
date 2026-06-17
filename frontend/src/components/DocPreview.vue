<script setup>
import { computed } from "vue"
import { marked } from "marked"
import { getDownloadUrl } from "../api.js"

const props = defineProps({
  task: { type: Object, required: true },
  progressSteps: { type: Array, default: () => [] },
})
const emit = defineEmits(["back", "delete"])

const STEP_LABELS = {
  searching:   { icon: "🔍", label: "搜索文档规范" },
  outline:     { icon: "📋", label: "生成大纲" },
  writing:     { icon: "✍️", label: "生成正文" },
  scoring:     { icon: "📊", label: "评分文档" },
  rewriting:   { icon: "🔄", label: "优化重写" },
  consistency: { icon: "🔗", label: "检查代码一致性" },
  done:        { icon: "✅", label: "完成" },
}

const timeline = computed(() => {
  const steps = props.progressSteps || []
  const map = {}
  const seenOrder = []

  for (const e of steps) {
    const key = e.step
    if (!STEP_LABELS[key]) continue
    if (!map[key]) {
      map[key] = { ...STEP_LABELS[key], key, status: "pending", details: [] }
      seenOrder.push(key)
    }
    const entry = map[key]
    if (e.status === "running") {
      entry.status = "running"
      if (e.detail) {
        // 同一条 detail 不重复添加
        if (!entry.details.includes(e.detail)) {
          entry.details.push(e.detail)
        }
      }
    } else if (e.status === "done") {
      entry.status = "done"
    }
  }

  // 按固定顺序排列，但只有出现过的才显示
  const order = ["searching", "outline", "writing", "scoring", "consistency", "rewriting", "done"]
  return order.filter(k => map[k]).map(k => map[k])
})

const html  = computed(() => props.task.result_md ? marked(props.task.result_md) : "")
const dlUrl = computed(() => getDownloadUrl(props.task.id))
</script>

<template>
  <div class="dv">
    <!-- 步骤时间线（running / pending 时显示） -->
    <div v-if="(task.status === 'running' || task.status === 'pending') && timeline.length > 0" class="tl-wrap">
      <div class="tl-inner">
        <div v-for="(item, i) in timeline" :key="item.key + '-' + i" class="tl-row">
          <!-- 圆点 + 竖线 -->
          <div class="tl-gutter">
            <div :class="['tl-dot', 'tl-dot--' + item.status]">
              <span v-if="item.status === 'done'" class="tl-check">✓</span>
              <span v-else-if="item.status === 'running'" class="tl-spin"></span>
            </div>
            <div v-if="i < timeline.length - 1" class="tl-line"></div>
          </div>
          <!-- 内容 -->
          <div class="tl-content">
            <div :class="['tl-label', { 'tl-label--active': item.status === 'running' }]">
              {{ item.icon }} {{ item.label }}
            </div>
            <div v-for="(d, di) in item.details" :key="di" class="tl-detail">{{ d }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- pending 且无步骤时，显示排队提示 -->
    <div v-else-if="task.status === 'pending'" class="banner s-pend">
      <span class="banner-icon">⏳</span>
      <span class="banner-text">任务已提交，正在排队…</span>
    </div>

    <!-- 失败 -->
    <div v-if="task.status === 'failed'" class="banner s-fail">
      <span class="banner-icon">❌</span>
      <span class="banner-text">文档生成失败</span>
      <span class="banner-err">：{{ task.error }}</span>
    </div>

    <!-- 失败操作栏 -->
    <div v-if="task.status === 'failed'" class="bar">
      <div class="bar-info">
        <span class="bar-icon">❌</span>
        <h2>{{ task.doc_type }}</h2>
      </div>
      <div class="bar-acts">
        <button class="act act--ghost" @click="emit('back')">返回列表</button>
        <button class="act act--del" @click="emit('delete', task.id)">删除</button>
      </div>
    </div>

    <!-- 完成 -->
    <template v-if="task.status === 'completed'">
      <div class="bar">
        <div class="bar-info">
          <span class="bar-icon">📄</span>
          <h2>{{ task.doc_type }}</h2>
        </div>
        <div class="bar-acts">
          <a :href="dlUrl" class="act act--fill" download>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            下载 MD
          </a>
          <button class="act act--ghost" @click="emit('back')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
            返回列表
          </button>
          <button class="act act--del" @click="emit('delete', task.id)">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
            删除
          </button>
        </div>
      </div>
      <div class="md" v-html="html"></div>
    </template>
  </div>
</template>

<style scoped>
.dv { min-height: 100%; display: flex; flex-direction: column }

/* ================================================================
   步骤时间线
   ================================================================ */
.tl-wrap {
  padding: 32px 40px;
  flex: 1;
}
.tl-inner {
  max-width: 520px;
  margin: 0 auto;
}
.tl-row {
  display: flex;
  gap: 16px;
  min-height: 48px;
}
.tl-gutter {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 24px;
  flex-shrink: 0;
}
.tl-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s ease;
}
.tl-dot--pending {
  background: #f1f5f9;
  border: 2px solid #e2e8f0;
}
.tl-dot--running {
  background: #dbeafe;
  border: 2px solid #3b82f6;
}
.tl-dot--done {
  background: #10b981;
  border: 2px solid #10b981;
}
.tl-check {
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
}
.tl-spin {
  width: 14px;
  height: 14px;
  border: 2px solid #93c5fd;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: rotate .7s linear infinite;
}
@keyframes rotate { to { transform: rotate(360deg) } }
.tl-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: #e2e8f0;
  margin: 4px 0;
  transition: background 0.3s;
}
.tl-content {
  padding-bottom: 20px;
  min-width: 0;
}
.tl-label {
  font-size: 15px;
  font-weight: 600;
  color: #94a3b8;
  transition: color 0.3s;
}
.tl-label--active {
  color: #1e40af;
  animation: stepFadeIn 0.35s ease;
}
@keyframes stepFadeIn {
  from { opacity: 0; transform: translateX(-6px) }
  to   { opacity: 1; transform: translateX(0) }
}
.tl-detail {
  font-size: 13px;
  color: #64748b;
  margin-top: 4px;
  padding: 4px 10px;
  background: #f8fafc;
  border-radius: 6px;
  display: inline-block;
  animation: stepFadeIn 0.35s ease;
}

/* ================================================================
   Banner（pending / failed 保留）
   ================================================================ */
.banner { display: flex; align-items: center; gap: 12px; padding: 20px 28px; font-size: 14px }
.banner-icon { font-size: 22px; flex-shrink: 0 }
.banner-text { font-weight: 500 }
.s-pend { background: linear-gradient(135deg, #fffbeb, #fef3c7); color: #92400e; border-bottom: 1px solid #fde68a }
.s-fail { background: linear-gradient(135deg, #fef2f2, #fee2e2); color: #991b1b; border-bottom: 1px solid #fecaca }
.banner-err { font-size: 13px; word-break: break-all }

/* ================================================================
   操作栏 & Markdown（完成状态，不变）
   ================================================================ */
.bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 28px;
  background: var(--surface, #fff);
  border-bottom: 1px solid var(--border, #e2e8f0);
  gap: 16px; flex-wrap: wrap;
}
.bar-info { display: flex; align-items: center; gap: 10px }
.bar-icon { font-size: 24px }
.bar-info h2 { font-size: 19px; font-weight: 700 }
.bar-acts { display: flex; gap: 8px; flex-wrap: wrap }

.act {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 9px 18px; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; text-decoration: none; border: none;
  min-height: 42px; transition: all .15s;
}
.act:active { transform: scale(.97) }
.act--fill {
  background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff;
  box-shadow: 0 2px 8px rgba(79,70,229,.25);
}
.act--fill:hover { box-shadow: 0 4px 14px rgba(79,70,229,.35) }
.act--ghost { background: #f1f5f9; color: #475569 }
.act--ghost:hover { background: #e2e8f0 }
.act--del { background: #fff; color: #dc2626; border: 1px solid #fecaca }
.act--del:hover { background: #fef2f2 }

/* ================================================================
   Markdown
   ================================================================ */
.md {
  max-width: 860px; margin: 0 auto; width: 100%;
  padding: 32px 28px 60px;
  font-size: 15px; line-height: 1.9; color: #334155;
  word-break: break-word;
}
.md :deep(h1) { font-size: 26px; margin: 0 0 20px; padding-bottom: 10px; border-bottom: 2px solid #f1f5f9; color: #0f172a; font-weight: 800; letter-spacing: -0.3px }
.md :deep(h2) { font-size: 20px; margin: 36px 0 14px; color: #1e293b; font-weight: 700 }
.md :deep(h3) { font-size: 17px; margin: 24px 0 10px; color: #334155; font-weight: 600 }
.md :deep(p)  { margin: 10px 0 }
.md :deep(ul), .md :deep(ol) { padding-left: 24px; margin: 8px 0 }
.md :deep(li) { margin: 4px 0 }
.md :deep(a)  { color: #4f46e5; text-decoration: underline; text-underline-offset: 2px; word-break: break-all }
.md :deep(a:hover) { color: #4338ca }
.md :deep(pre) { background: #1e293b; padding: 20px; border-radius: 12px; overflow-x: auto; margin: 16px 0; -webkit-overflow-scrolling: touch }
.md :deep(pre code) { color: #e2e8f0; font-family: "SF Mono","Fira Code","Cascadia Code","Consolas",monospace; font-size: 13px; line-height: 1.7; background: none; padding: 0 }
.md :deep(code) { background: #f1f5f9; padding: 2px 6px; border-radius: 5px; font-size: 13px; color: #e11d48; font-weight: 500 }
.md :deep(table) {
  width: 100%; table-layout: auto;
  border-collapse: separate; border-spacing: 0;
  margin: 18px 0; font-size: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,.04);
}
.md :deep(th) {
  background: #f1f5f9; font-weight: 600; text-align: left;
  white-space: nowrap; font-size: 13px;
  color: #475569; letter-spacing: .3px;
}
.md :deep(th), .md :deep(td) {
  border-bottom: 1px solid #e2e8f0;
  border-right: 1px solid #e2e8f0;
  padding: 10px 16px;
}
.md :deep(th):last-child, .md :deep(td):last-child { border-right: none }
.md :deep(tr):last-child td { border-bottom: none }
.md :deep(tr:nth-child(even)) td { background: #f8fafc }
.md :deep(tr:hover) td { background: #eef2ff }
.md :deep(blockquote) { border-left: 4px solid #4f46e5; padding: 12px 20px; margin: 16px 0; color: #64748b; background: #f8fafc; border-radius: 0 10px 10px 0; font-style: italic }
.md :deep(hr) { border: none; border-top: 1px solid #e2e8f0; margin: 28px 0 }
.md :deep(img) { max-width: 100%; height: auto; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.06) }
.md :deep(strong) { color: #0f172a; font-weight: 700 }

/* ================================================================
   手机端
   ================================================================ */
@media (max-width: 640px) {
  .md :deep(table) { display: block; overflow-x: auto; -webkit-overflow-scrolling: touch }
  .md { padding: 24px 16px 48px; font-size: 14px }
  .bar { padding: 16px 20px }
  .bar-acts { width: 100% }
  .banner { padding: 16px 20px; font-size: 13px }
  .tl-wrap { padding: 24px 20px }
}
</style>