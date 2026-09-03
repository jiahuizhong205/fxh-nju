<script setup lang="ts">
import { ref } from 'vue'

const accounts = ref([
  { name: '小林同学', major: '新闻学院 · 新闻学', current: true, star: true, avatar: '/illustrations/avatar-wreath.png' },
  { name: '张同学', major: '计算机科学与技术', current: false, star: false, avatar: '/illustrations/avatar-2.png' },
  { name: '李同学', major: '经济学', current: false, star: false, avatar: '/illustrations/avatar-3.png' },
])

function switchTo(acc: (typeof accounts.value)[number]) {
  accounts.value.forEach((a) => (a.current = a === acc))
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/settings" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>切换账号</h2>
    </header>

    <p class="page-sub">换一位园丁 🌿</p>

    <section class="card" style="padding: 0; overflow: hidden;">
      <div v-for="a in accounts" :key="a.major" class="account" @click="switchTo(a)">
        <img class="avatar" :src="a.avatar" alt="" />
        <div class="acc-info">
          <div class="acc-name">{{ a.name }} <span v-if="a.star">⭐</span></div>
          <div class="acc-major">{{ a.major }}</div>
        </div>
        <button v-if="a.current" class="current">当前园丁</button>
        <button v-else class="switch">切换</button>
      </div>
    </section>

    <button class="btn-ghost">🌱 添加新账号</button>
    <p class="foot">切换账号后福小禾会按新园丁的土壤条件重新推荐 🍀</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.account { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--bg-subtle); cursor: pointer; }
.account:last-child { border-bottom: none; }
.avatar { width: 40px; height: 40px; border-radius: var(--radius-full); object-fit: cover; flex-shrink: 0; }
.acc-info { flex: 1; }
.acc-name { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.acc-major { font-size: var(--text-xs); color: var(--text-muted); margin-top: var(--space-1); }
.current { padding: var(--space-1) var(--space-3); background: var(--bg-green-faint); color: var(--brand-strong); border-radius: var(--radius-full); font-size: var(--text-2xs); border: none; cursor: default; }
.switch { padding: var(--space-1) var(--space-3); background: #fff; color: var(--text-secondary); border: 1px solid var(--border); border-radius: var(--radius-full); font-size: var(--text-2xs); cursor: pointer; font-family: inherit; }
.btn-ghost { width: 100%; margin-top: var(--space-4); padding: var(--space-3); border: 1px dashed var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
