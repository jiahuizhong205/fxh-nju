<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProfile, updateProfile } from '../api/client'
import BackButton from '../components/BackButton.vue'

const router = useRouter()
const route = useRoute()

const moods = ref([
  { name: '晨光', icon: '🌅', active: false },
  { name: '黄金档', icon: '☀️', active: true },
  { name: '暮色', icon: '🌆', active: false },
])

const slots = ['早八战士', '上午黄金档', '午后时光', '晚间高效派', '随意灵活']
const selected = ref<string[]>(['上午黄金档', '午后时光'])

const concentration = ref('均匀分散')
const concentrationOpts = ['集中授课', '均匀分散', '每周几天高强度其余自由']

const nap = ref('需要午休')
const napOpts = ['需要午休', '午休灵活', '无需午休']

function toggleSlot(s: string) {
  const i = selected.value.indexOf(s)
  if (i >= 0) selected.value.splice(i, 1)
  else selected.value.push(s)
}

function pickMood(name: string) {
  moods.value.forEach(m => (m.active = m.name === name))
}

onMounted(async () => {
  const p = await fetchProfile()
  const sp = p?.schedule_preferences as Record<string, any> | undefined
  if (!sp) return
  if (sp.energy_period) pickMood(sp.energy_period)
  if (Array.isArray(sp.time_slots) && sp.time_slots.length) selected.value = sp.time_slots
  if (sp.concentration) concentration.value = sp.concentration
  if (sp.nap) nap.value = sp.nap
})

async function save() {
  const energy = moods.value.find(m => m.active)?.name ?? ''
  await updateProfile({
    schedule_preferences: {
      energy_period: energy,
      time_slots: selected.value,
      concentration: concentration.value,
      nap: nap.value,
      prefer_late: selected.value.includes('晚间高效派'),
    },
  })
  router.push(route.query.onboarding === '1' ? { path: '/interest-selection', query: { onboarding: '1', stage: '2' } } : '/conflict-resolution')
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/course-planning" />
      <h2>排课时间偏好</h2>
    </header>

    <p class="page-sub">阳光最好的时间 ☀️</p>

    <div class="illus"><img src="/illustrations/time-preference.png" alt="" /></div>

    <section class="card">
      <h4 class="card-title"><span class="title-icon">⚗</span> 你最喜欢的上课时间段 <span class="hint">可多选</span></h4>
      <div class="slots">
        <button v-for="s in slots" :key="s" class="chip" :class="{ selected: selected.includes(s) }" @click="toggleSlot(s)">
          {{ s }}
        </button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title"><span class="title-icon green">⊗</span> 课程集中度偏好</h4>
      <div class="choice-list">
        <button v-for="c in concentrationOpts" :key="c" class="choice" :class="{ selected: concentration === c }" @click="concentration = c">
          <span>{{ c }}</span>
          <span class="radio" :class="{ on: concentration === c }" />
        </button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title"><span class="title-icon purple">☾</span> 午休习惯</h4>
      <div class="chips">
        <button v-for="n in napOpts" :key="n" class="chip" :class="{ selected: nap === n }" @click="nap = n">{{ n }}</button>
      </div>
    </section>

    <button class="btn-primary" @click="save">保存时间偏好</button>
    <p class="foot">福小禾会根据你的时间偏好优化课表推荐 🌻</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100%; max-width: 342px; height: auto; }
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.hint { font-size: var(--text-xs); font-weight: var(--weight-normal); color: var(--text-muted); margin-left: var(--space-1); }
.title-icon { color: #76558b; font-size: var(--text-lg); }
.title-icon.green { color: var(--brand); }
.title-icon.purple { color: #76558b; }

.slots { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.slots .chip.selected { background: #fff5d8; border-color: #f1d17a; color: #9a6b17; }
.card:last-of-type .chip.selected { background: #d8c8e4; border-color: #8b669f; color: #76558b; }
.choice-list { display: flex; flex-direction: column; gap: var(--space-2); }
.choice { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); width: 100%; padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-md); background: var(--bg-surface); color: var(--text-primary); font: inherit; font-size: var(--text-sm); text-align: left; cursor: pointer; }
.choice.selected { border-color: var(--brand); background: var(--bg-green-soft); color: var(--brand-strong); font-weight: var(--weight-semibold); }
.radio { width: 18px; height: 18px; border: 2px solid var(--border); border-radius: 50%; flex-shrink: 0; }
.radio.on { border-color: var(--brand); background: var(--brand); box-shadow: inset 0 0 0 4px var(--bg-surface); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
