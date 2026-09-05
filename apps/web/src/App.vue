<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  { to: '/', label: '花园', icon: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-6h6v6"/>' },
  { to: '/career', label: '探索', icon: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>' },
  { to: '/course-planning', label: '日程', icon: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>' },
  { to: '/profile', label: '我的', icon: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.66V19a5 5 0 0 1 10 0v1.66"/>' },
]

function isActive(path: string) {
  return path === '/' ? route.path === '/' : route.path.startsWith(path)
}
</script>

<template>
  <div v-if="route.name === 'login'" class="app app-plain">
    <RouterView />
  </div>
  <div v-else class="app">
    <header v-if="route.name !== 'recommend' && route.name !== 'course-planning' && route.name !== 'job-detail'" class="app-header">
      <h1>福小禾</h1>
      <span class="subtitle">南大复合型人才学习助手</span>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
    <nav class="tab-bar">
      <router-link
        v-for="t in tabs"
        :key="t.to"
        :to="t.to"
        class="tab"
        :class="{ active: isActive(t.to) }"
      >
        <svg
          viewBox="0 0 24 24"
          width="22"
          height="22"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          v-html="t.icon"
        ></svg>
        <span>{{ t.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-sans);
  background: var(--bg-subtle);
  color: var(--text-primary);
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 480px;
  margin: 0 auto;
  background: var(--bg-page);
  box-shadow: 0 0 32px rgba(0, 0, 0, 0.08);
}

.app-plain {
  box-shadow: none;
}

.app.app .app-header {
  display: flex !important;
  align-items: baseline;
  gap: 8px;
  padding: 14px 16px;
  background: var(--brand-ink);
  color: #fff;
  flex-shrink: 0;
}

.app-header h1 {
  font-size: var(--text-xl);
  font-weight: var(--weight-bold);
}

.app-header .subtitle {
  font-size: var(--text-xs);
  opacity: 0.85;
}

.app-main {
  flex: 1;
  overflow-y: auto;
}

.app.app .tab-bar {
  flex-shrink: 0;
  display: flex !important;
  background: var(--bg-surface);
  border-top: 1px solid var(--border);
}

.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 0 8px;
  color: var(--text-muted);
  text-decoration: none;
  font-size: var(--text-2xs);
}

.tab.active {
  color: var(--brand-strong);
  font-weight: var(--weight-semibold);
}
</style>
