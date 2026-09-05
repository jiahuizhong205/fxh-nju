<script setup lang="ts">
import BackButton from '../components/BackButton.vue'

const groups = [
  {
    title: '🧑‍🌾 账户与资料',
    items: [
      { to: '/edit-profile', label: '编辑个人资料', desc: '🌱 我的园丁卡片' },
      { to: '/settings/switch-account', label: '切换账号', desc: '🔄 换一位园丁' },
      { to: '/settings/bind-contact', label: '绑定手机/邮箱', desc: '📱 花园联络方式' },
    ],
  },
  {
    title: '🔔 通知与提醒',
    items: [
      { to: '/settings/learning-reminder', label: '学习提醒频次', desc: '💧 浇水节奏' },
      { to: '/settings/job-push', label: '岗位推送偏好', desc: '📬 新花开在哪片地？' },
    ],
  },
  {
    title: '🪴 学习偏好',
    items: [
      { to: '/time-preference', label: '排课时间偏好', desc: '⏰ 阳光最好的时辰' },
      { to: '/conflict-resolution', label: '辅修冲突处理', desc: '🔀 藤蔓绕路方式：免修不免考 / 跨校区通勤' },
    ],
  },
  {
    title: '🏺 数据与存储',
    items: [
      { to: '/settings/clear-cache', label: '清除缓存', desc: '🍂 扫走枯叶' },
    ],
  },
  {
    title: '🍀 关于与支持',
    items: [
      { to: '/settings/about', label: '关于福小禾', desc: '📖 物种起源 v2.1.4' },
      { to: '/settings/feedback', label: '意见反馈', desc: '💬 给园丁写信' },
    ],
  },
]
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <h2>花园工具箱</h2>
    </header>
    <div class="illus"><img src="/illustrations/settings-header.png" alt="" /></div>
    <p class="page-sub">调整你的成长环境 🌿</p>

    <section v-for="g in groups" :key="g.title" class="group-wrap">
      <h3 class="group-title">{{ g.title }}</h3>
      <div class="group">
        <router-link v-for="item in g.items" :key="item.to" :to="item.to" class="setting-row">
          <span class="row-main">
            <span class="row-label">{{ item.label }}</span>
            <span class="row-desc">{{ item.desc }}</span>
          </span>
          <svg class="chevron" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m9 18 6-6-6-6"/>
          </svg>
        </router-link>
      </div>
    </section>

  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100%; max-width: 390px; height: auto; }
.group-wrap { margin-bottom: var(--space-4); }
.group-title { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--text-secondary); margin-bottom: var(--space-2); padding-left: var(--space-1); }
.group { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.setting-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); text-decoration: none; border-bottom: 1px solid var(--bg-subtle); }
.setting-row:last-child { border-bottom: none; }
.row-main { display: flex; flex-direction: column; gap: 2px; }
.row-label { font-size: var(--text-base); color: var(--text-primary); font-weight: var(--weight-medium); }
.row-desc { font-size: var(--text-xs); color: var(--text-muted); }
.chevron { color: var(--text-muted); flex-shrink: 0; }
</style>
