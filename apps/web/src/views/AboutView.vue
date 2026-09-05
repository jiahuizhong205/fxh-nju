<script setup lang="ts">
import BackButton from '../components/BackButton.vue'

const version = 'v2.1.4'
const features = [
  { icon: '🌱', label: '辅修政策答疑' },
  { icon: '🌸', label: '辅修专业推荐' },
  { icon: '🌿', label: '个性化课程规划' },
  { icon: '🌳', label: '复合方向伴学' },
  { icon: '🌻', label: '职业方向探索' },
]
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>关于福小禾</h2>
    </header>

    <p class="page-sub">物种起源</p>

    <section class="about">
      <div class="logo">
        <img src="/illustrations/mascot.png" alt="" />
      </div>
      <h3 class="brand">福小禾</h3>
      <p class="version">{{ version }}</p>
      <p class="desc">南京大学 · 复合型人才成长助手</p>
    </section>

    <section class="card facts">
      <div class="fact-row"><span class="fk">诞生年份</span><span class="fv">2026年</span></div>
      <div class="fact-row"><span class="fk">物种归属</span><span class="fv">南京大学 · 三三制花园</span></div>
      <div class="fact-row"><span class="fk">核心使命</span><span class="fv">让每一颗种子长成复合型大树</span></div>
      <div class="fact-row"><span class="fk">开发团队</span><span class="fv">福小禾花园工作室</span></div>
    </section>

    <section class="card features">
      <div v-for="f in features" :key="f.label" class="feature-row">
        <span class="feature-icon">{{ f.icon }}</span>
        <span class="feature-label">{{ f.label }}</span>
      </div>
    </section>

    <p class="foot">福小禾会持续生长，陪你走过南大每一季 🌾</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.about { display: flex; flex-direction: column; align-items: center; text-align: center; padding: var(--space-6) var(--space-4); }
.logo { width: 72px; height: 72px; border-radius: var(--radius-xl); background: var(--bg-green-soft); color: var(--brand-strong); display: flex; align-items: center; justify-content: center; }
.logo img { width: 100%; height: 100%; object-fit: contain; }
.brand { margin-top: var(--space-3); font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.version { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--text-muted); }
.desc { margin-top: var(--space-2); font-size: var(--text-base); color: var(--text-secondary); }

.facts { padding: 0; overflow: hidden; }
.fact-row { display: flex; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--bg-subtle); }
.fact-row:last-child { border-bottom: none; }
.fk { font-size: var(--text-sm); color: var(--text-muted); flex-shrink: 0; }
.fv { font-size: var(--text-sm); color: var(--text-primary); text-align: right; }

.features { padding: 0; overflow: hidden; }
.feature-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--bg-subtle); }
.feature-row:last-child { border-bottom: none; }
.feature-icon { font-size: var(--text-xl); }
.feature-label { font-size: var(--text-base); color: var(--text-primary); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
