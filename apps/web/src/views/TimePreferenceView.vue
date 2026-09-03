<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, updateProfile } from '../api/client'

const router = useRouter()

const moods = ref([
  { name: '晨光', icon: '🌅', active: false },
  { name: '黄金档', icon: '☀️', active: false },
  { name: '暮色', icon: '🌆', active: false },
])

const slots = ['早八战士', '上午黄金档', '午后时光', '晚间高效派', '随意灵活']
const selected = ref<string[]>([])

const concentration = ref('集中授课')
const concentrationOpts = ['集中授课', '均匀分散']

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
  if (Array.isArray(sp.time_slots)) selected.value = sp.time_slots
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
  router.push('/conflict-resolution')
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/course-planning" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>排课时间偏好</h2>
    </header>

    <p class="page-sub">阳光最好的时间 ☀️</p>

    <div class="illus"><img src="/illustrations/time-preference.png" alt="" /></div>

    <section class="card">
      <h4 class="card-title">能量时段</h4>
      <div class="moods">
        <button v-for="m in moods" :key="m.name" class="mood" :class="{ active: m.active }" @click="pickMood(m.name)">
          <span class="mood-icon">{{ m.icon }}</span>
          <span class="mood-name">{{ m.name }}</span>
        </button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">你最喜欢的上课时间段 <span class="hint">可多选</span></h4>
      <div class="slots">
        <button v-for="s in slots" :key="s" class="chip" :class="{ selected: selected.includes(s) }" @click="toggleSlot(s)">
          {{ s }}
        </button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">课程集中度偏好</h4>
      <div class="chips">
        <button v-for="c in concentrationOpts" :key="c" class="chip" :class="{ selected: concentration === c }" @click="concentration = c">{{ c }}</button>
      </div>
      <p class="desc">每周几天高强度其余自由</p>
    </section>

    <section class="card">
      <h4 class="card-title">午休习惯</h4>
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

.moods { display: flex; gap: var(--space-3); }
.mood { flex: 1; display: flex; flex-direction: column; align-items: center; gap: var(--space-2); padding: var(--space-3); border: 1px solid var(--border); background: var(--bg-surface); border-radius: var(--radius-md); cursor: pointer; font-family: inherit; }
.mood.active { border-color: var(--brand); background: var(--bg-green-faint); }
.mood-icon { font-size: var(--text-2xl); }
.mood-name { font-size: var(--text-sm); color: var(--text-secondary); }
.mood.active .mood-name { color: var(--brand-strong); font-weight: var(--weight-semibold); }

.slots { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.desc { margin-top: var(--space-2); font-size: var(--text-xs); color: var(--text-muted); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
