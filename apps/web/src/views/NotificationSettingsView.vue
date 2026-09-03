<script setup lang="ts">
import { ref } from 'vue'

const settings = ref([
  { icon: '📚', label: '学习浇水提醒', desc: '每周学习计划推送', on: true },
  { icon: '🌸', label: '新岗位开花推送', desc: '复合背景岗位上新提醒', on: true },
  { icon: '🍃', label: '政策藤蔓更新', desc: '辅修政策、培养方案变动', on: true },
  { icon: '🧭', label: '推荐报告完成', desc: '辅修推荐报告生成通知', on: false },
  { icon: '📅', label: '课表冲突预警', desc: '新学期排课冲突提醒', on: true },
])
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/profile" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>通知设置</h2>
    </header>

    <div class="illus"><img src="/illustrations/windbell.png" alt="" /></div>

    <p class="page-sub">风铃要响几声？ 🌿</p>

    <section class="card" style="padding: 0; overflow: hidden;">
      <div v-for="s in settings" :key="s.label" class="row">
        <span class="row-icon">{{ s.icon }}</span>
        <div class="row-main">
          <div class="row-label">{{ s.label }}</div>
          <div class="row-desc">{{ s.desc }}</div>
        </div>
        <div class="toggle" :class="{ on: s.on }" @click="s.on = !s.on">
          <div class="knob"></div>
        </div>
      </div>
    </section>

    <button class="btn-primary">保存风铃偏好</button>
    <p class="foot">关闭后，对应消息将不再通过风铃通知你 🌿</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100%; max-width: 390px; height: auto; }
.row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--bg-subtle); }
.row:last-child { border-bottom: none; }
.row-icon { font-size: var(--text-xl); flex-shrink: 0; }
.row-main { flex: 1; }
.row-label { font-size: var(--text-base); color: var(--text-primary); }
.row-desc { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
