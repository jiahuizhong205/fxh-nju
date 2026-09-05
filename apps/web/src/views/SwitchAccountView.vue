<script setup lang="ts">
import { ref } from 'vue'
import BackButton from '../components/BackButton.vue'

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
      <BackButton fallback="/settings" />
      <h2>切换账号</h2>
    </header>

    <p class="page-sub">换一位园丁 🌿</p>

    <section class="card current-card">
      <template v-for="a in accounts" :key="a.major">
        <div v-if="a.current" class="account current-account">
          <img class="avatar current-avatar" :src="a.avatar" alt="" />
          <div class="acc-info">
            <div class="acc-name">{{ a.name }} <span v-if="a.star">⭐</span></div>
            <div class="acc-major">{{ a.major }}</div>
          </div>
          <span class="current">当前园丁</span>
        </div>
      </template>
    </section>

    <div class="account-divider" aria-hidden="true"><span>✿</span></div>

    <section class="account-list">
      <template v-for="a in accounts" :key="a.major">
        <button v-if="!a.current" class="card account account-option" :aria-label="`切换到${a.name}`" @click="switchTo(a)">
          <img class="avatar" :src="a.avatar" alt="" />
          <span class="acc-info">
            <span class="acc-name">{{ a.name }} <span v-if="a.star">⭐</span></span>
            <span class="acc-major">{{ a.major }}</span>
          </span>
          <span class="switch">切换</span>
        </button>
      </template>
    </section>

    <button class="btn-ghost">🌱 添加新账号</button>
    <p class="foot">切换账号后福小禾会按新园丁的土壤条件重新推荐 🍀</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.current-card { border-color: var(--bg-green-soft); padding: var(--space-4); }
.account { display: flex; align-items: center; gap: var(--space-3); }
.current-account { min-height: 64px; }
.account-list { display: flex; flex-direction: column; gap: var(--space-3); }
.account-option { width: 100%; padding: var(--space-3) var(--space-4); border-color: var(--bg-green-soft); background: var(--bg-surface); cursor: pointer; font: inherit; text-align: left; }
.avatar { width: 40px; height: 40px; border-radius: var(--radius-full); object-fit: cover; flex-shrink: 0; }
.current-avatar { width: 64px; height: 64px; }
.acc-info { flex: 1; }
.acc-name { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.acc-major { font-size: var(--text-xs); color: var(--text-muted); margin-top: var(--space-1); }
.current { padding: var(--space-1) var(--space-3); background: var(--bg-green-faint); color: var(--brand-strong); border-radius: var(--radius-full); font-size: var(--text-2xs); border: none; cursor: default; }
.switch { padding: var(--space-1) var(--space-3); background: #fff; color: var(--text-secondary); border: 1px solid var(--border); border-radius: var(--radius-full); font-size: var(--text-2xs); cursor: pointer; font-family: inherit; }
.account-divider { display: flex; align-items: center; gap: var(--space-3); margin: var(--space-2) 0; color: var(--accent-purple); }
.account-divider::before, .account-divider::after { content: ''; height: 1px; flex: 1; background: var(--bg-subtle); }
.account-divider span { font-size: var(--text-base); }
.btn-ghost { width: 100%; margin-top: var(--space-4); padding: var(--space-3); border: 1px solid var(--brand); background: #fff; border-radius: var(--radius-full); font-size: var(--text-sm); color: var(--brand-strong); cursor: pointer; font-family: inherit; font-weight: var(--weight-semibold); }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
