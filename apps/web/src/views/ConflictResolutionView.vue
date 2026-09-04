<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, updateProfile } from '../api/client'

const router = useRouter()

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/course-planning')
}

const strategies = [
  { icon: '📝', name: '免修不免考申请', desc: '申请免修不免考，主修/辅修冲突课程可自学参加考试', note: '需向院系提交申请，部分课程适用', enabled: true },
  { icon: '🚌', name: '跨校区通勤', desc: '跨校区通勤上课，仙林↔鼓楼/苏州', note: '单程约40-60分钟，适合每周1-2次课程', enabled: false },
  { icon: '💻', name: '优先选择线上/混合课程', desc: '优先选择支持线上或混合式教学的辅修课程', note: '部分课程提供录播或同步直播', enabled: false },
  { icon: '📅', name: '放弃冲突课程/延后修读', desc: '放弃冲突课程，延后至下一学年/学期修读', note: '可能延长辅修完成时间', enabled: false },
  { icon: '🔄', name: '申请课程替换/学分互认', desc: '申请用主修课程替换辅修相近课程', note: '需经辅修院系审核批准', enabled: false },
]

function toggle(s: (typeof strategies)[number]) {
  s.enabled = !s.enabled
}

onMounted(async () => {
  const p = await fetchProfile()
  const sp = p?.schedule_preferences as Record<string, any> | undefined
  const saved: string[] = sp?.conflict_strategies ?? []
  if (!saved.length) return
  strategies.forEach(s => (s.enabled = saved.includes(s.name)))
})

async function save() {
  const enabled = strategies.filter(s => s.enabled).map(s => s.name)
  await updateProfile({ schedule_preferences: { conflict_strategies: enabled } })
  router.push('/recommend')
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/course-planning" class="back" @click.prevent="goBack">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>辅修冲突处理</h2>
    </header>

    <p class="page-sub">藤蔓绕路方式 🌿</p>

    <section v-for="s in strategies" :key="s.name" class="card strategy" :class="{ enabled: s.enabled }" @click="toggle(s)">
      <span class="strategy-icon">{{ s.icon }}</span>
      <div class="strategy-body">
        <div class="strategy-name">{{ s.name }}</div>
        <div class="strategy-desc">{{ s.desc }}</div>
        <div class="strategy-note">{{ s.note }}</div>
      </div>
      <div class="toggle" :class="{ on: s.enabled }">
        <div class="knob"></div>
      </div>
    </section>

    <p class="tip">以上策略可组合使用，福小禾会按优先级自动优化排课 🌱</p>

    <button class="btn-primary" @click="save">保存冲突处理偏好</button>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.strategy { display: flex; align-items: flex-start; gap: var(--space-3); cursor: pointer; }
.strategy.enabled { border-color: var(--brand); }
.strategy-icon { font-size: var(--text-2xl); flex-shrink: 0; }
.strategy-body { flex: 1; }
.strategy-name { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.strategy-desc { margin-top: 2px; font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.5; }
.strategy-note { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.tip { font-size: var(--text-xs); color: var(--text-secondary); line-height: 1.6; text-align: center; }
</style>
