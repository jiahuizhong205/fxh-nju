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
  <div class="page about-page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>关于福小禾</h2>
    </header>

    <p class="page-sub">物种起源</p>

    <section class="about">
      <div class="logo">
        <img src="/illustrations/mascot.png" alt="福小禾幼苗标志" />
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

    <section class="feature-list" aria-label="福小禾功能">
      <div v-for="f in features" :key="f.label" class="feature-chip">
        <span class="feature-icon">{{ f.icon }}</span>
        <span class="feature-label">{{ f.label }}</span>
      </div>
    </section>

    <p class="foot">福小禾会持续生长，陪你走过南大每一季 🌾</p>
  </div>
</template>

<style scoped>
.about-page { min-height: 100%; gap: var(--space-4); padding: var(--space-4) var(--space-5) var(--space-5); }
.about-page .page-head { position: relative; justify-content: center; }
.about-page .page-head .back { position: absolute; left: 0; }
.about-page .page-head h2 { font-size: var(--text-2xl); }
.about-page .page-sub { margin: calc(var(--space-1) * -1) 0 0; text-align: center; color: var(--brand); font-size: var(--text-md); font-weight: var(--weight-semibold); }
.about { display: flex; flex-direction: column; align-items: center; text-align: center; padding: var(--space-4) var(--space-4) var(--space-3); }
.logo { width: 124px; height: 124px; display: flex; align-items: center; justify-content: center; }
.logo img { width: 100%; height: 100%; object-fit: contain; }
.brand { margin-top: var(--space-4); font-size: var(--text-5xl); line-height: 1.1; font-weight: var(--weight-bold); color: var(--text-primary); }
.version { margin-top: var(--space-2); padding: 3px var(--space-3); border-radius: var(--radius-full); background: #eee8f2; color: var(--accent-purple); font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.desc { margin-top: var(--space-3); font-size: var(--text-md); font-weight: var(--weight-semibold); color: var(--brand-strong); }

.facts { padding: 0 var(--space-5); overflow: hidden; border: none; border-radius: var(--radius-2xl); box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.fact-row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--bg-subtle); }
.fact-row:last-child { border-bottom: none; }
.fk { font-size: var(--text-sm); color: var(--text-muted); flex-shrink: 0; }
.fv { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); text-align: right; }

.feature-list { display: flex; flex-wrap: wrap; gap: var(--space-3); padding: 0; }
.feature-chip { display: inline-flex; align-items: center; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-radius: var(--radius-full); background: var(--bg-surface); box-shadow: 0 5px 14px rgba(81, 94, 76, 0.1); }
.feature-icon { font-size: var(--text-lg); line-height: 1; }
.feature-label { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--text-primary); }
.foot { margin-top: auto; padding-top: var(--space-6); text-align: center; font-size: var(--text-sm); color: var(--text-muted); }
</style>
