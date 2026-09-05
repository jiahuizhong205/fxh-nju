<script setup lang="ts">
import { ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const times = ['上午 09:00', '下午 14:00', '晚上 20:00']
const time = ref('上午 09:00')
const customTime = ref('')

const frequency = ref('每日浇水')
const freqOptions = ['每日浇水', '隔日浇水', '每周浇水', '仅工作日', '自定义']

const weekDays = ['一', '二', '三', '四', '五', '六', '日']
const week = ref<string[]>(['一', '三', '五'])

function toggleDay(d: string) {
  const i = week.value.indexOf(d)
  if (i >= 0) week.value.splice(i, 1)
  else week.value.push(d)
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>学习提醒频次</h2>
    </header>

    <p class="page-sub">浇水节奏 🌱</p>

    <div class="illus"><img src="/illustrations/watering.png" alt="" /></div>

    <section class="card reminder-card">
      <h4 class="card-title">☀️ 每日提醒时间</h4>
      <div class="chips">
        <button v-for="t in times" :key="t" class="chip" :class="{ selected: time === t }" @click="time = t">{{ t }}</button>
        <button class="chip" :class="{ selected: time === '自定义' }" @click="time = '自定义'">自定义</button>
      </div>
      <input v-model="customTime" class="custom-time" type="text" inputmode="numeric" placeholder="输入具体时间，如 19:30" aria-label="自定义提醒时间" @focus="time = '自定义'" />
    </section>

    <section class="card reminder-card">
      <h4 class="card-title">📅 提醒频次</h4>
      <div class="chips">
        <button v-for="f in freqOptions" :key="f" class="chip" :class="{ selected: frequency === f }" @click="frequency = f">{{ f }}</button>
      </div>
      <div v-if="frequency === '每周浇水'" class="weekly-days">
        <h4 class="days-title">选择每周浇水日：</h4>
        <div class="days">
          <button v-for="d in weekDays" :key="d" class="day" :class="{ selected: week.includes(d) }" @click="toggleDay(d)">{{ d }}</button>
        </div>
      </div>
    </section>

    <button class="btn-primary">保存浇水节奏 🌿</button>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100px; height: 100px; }
.reminder-card { border-color: var(--bg-green-soft); }
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.custom-time { width: 100%; margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--bg-green-soft); border-radius: var(--radius-md); background: var(--bg-green-faint); color: var(--text-primary); font: inherit; font-size: var(--text-sm); outline: none; }
.custom-time:focus { border-color: var(--brand); }
.weekly-days { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--bg-green-soft); }
.days-title { margin-bottom: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary); font-weight: var(--weight-medium); }
.days { display: flex; gap: var(--space-2); }
.day { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--border); background: #fff; font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; display: flex; align-items: center; justify-content: center; }
.day.selected { background: var(--bg-green-soft); color: var(--brand-strong); border-color: var(--brand); }
</style>
