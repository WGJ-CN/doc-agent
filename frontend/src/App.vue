<script setup>
import { computed } from "vue"
import { useRouter, useRoute } from "vue-router"

const router = useRouter()
const route = useRoute()

const activeTab = computed(() => route.name || "doc")

function goDoc()  { router.push({ name: "doc" }) }
function goTest() { router.push({ name: "test" }) }
</script>

<template>
  <div class="app-shell">
    <!-- 顶部导航 -->
    <nav class="nav-bar">
      <div class="nav-brand">Agent</div>
      <div class="nav-tabs">
        <button
          :class="['nav-tab', { 'nav-tab--active': activeTab === 'doc' }]"
          @click="goDoc"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
          <span>文档生成</span>
        </button>
        <button
          :class="['nav-tab', { 'nav-tab--active': activeTab === 'test' }]"
          @click="goTest"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/></svg>
          <span>测试用例</span>
        </button>
      </div>
    </nav>

    <!-- 页面内容 -->
    <div class="page-container">
      <router-view />
    </div>
  </div>
</template>

<style>
/* ================================================================
   全局变量 & 基础重置
   ================================================================ */
:root {
  --safe-top:    env(safe-area-inset-top, 0px);
  --bg:          #f8fafc;
  --surface:     #ffffff;
  --border:      #e2e8f0;
  --text:        #0f172a;
  --text-soft:   #475569;
  --text-muted:  #94a3b8;
  --primary:     #4f46e5;
  --radius:      10px;
}
*,*::before,*::after{box-sizing:border-box}html,body{margin:0;padding:0}html,body,#app{height:100%}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;-webkit-tap-highlight-color:transparent}
</style>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 导航栏 */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 16px;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  user-select: none;
}
.nav-brand {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: -0.3px;
  color: var(--text);
}
.nav-tabs {
  display: flex;
  gap: 4px;
}
.nav-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  background: none;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.nav-tab:hover {
  color: var(--text-soft);
  background: #f1f5f9;
}
.nav-tab--active {
  color: var(--primary);
  background: #eef2ff;
}
.nav-tab--active:hover {
  background: #e0e7ff;
}

/* 页面容器 */
.page-container {
  height: calc(100vh - 48px);
}

/* 手机端缩小 nav */
@media (max-width: 959px) {
  .nav-bar {
    height: 44px;
    padding: 0 12px;
    padding-top: var(--safe-top);
  }
  .page-container {
    height: calc(100vh - 44px - var(--safe-top));
  }
  .nav-brand {
    font-size: 14px;
  }
  .nav-tab {
    padding: 5px 10px;
    font-size: 12px;
  }
  .nav-tab svg {
    width: 14px;
    height: 14px;
  }
}
</style>
