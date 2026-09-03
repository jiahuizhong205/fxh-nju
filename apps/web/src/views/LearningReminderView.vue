<script setup lang="ts">
import { ref } from 'vue'

const times = ['上午 09:00', '下午 14:00', '晚上 20:00']
const time = ref('上午 09:00')

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
      <router-link to="/settings" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>学习提醒频次</h2>
    </header>

    <p class="page-sub">浇水节奏 🌱</p>

    <div class="illus"><img src="/illustrations/watering.png" alt="" /></div>

    <section class="card">
      <h4 class="card-title">☀️ 每日提醒时间</h4>
      <div class="chips">
        <button v-for="t in times" :key="t" class="chip" :class="{ selected: time === t }" @click="time = t">{{ t }}</button>
        <button class="chip">自定义</button>
      </div>
      <p class="hint">输入具体时间，如 19:30</p>
    </section>

    <section class="card">
      <h4 class="card-title">📅 提醒频次</h4>
      <div class="chips">
        <button v-for="f in freqOptions" :key="f" class="chip" :class="{ selected: frequency === f }" @click="frequency = f">{{ f }}</button>
      </div>
    </section>

    <section v-if="frequency === '每周浇水'" class="card">
      <h4 class="card-title">选择每周浇水日：</h4>
      <div class="days">
        <button v-for="d in weekDays" :key="d" class="day" :class="{ selected: week.includes(d) }" @click="toggleDay(d)">{{ d }}</button>
      </div>
    </section>

    <button class="btn-primary">保存浇水节奏 🌿</button>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100px; height: 100px; }
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.hint { margin-top: var(--space-2); font-size: var(--text-xs); color: var(--text-muted); }
.days { display: flex; gap: var(--space-2); }
.day { width: 36px; height: 36px; border-radius: 50%; border: 1px solid var(--border); background: #fff; font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; display: flex; align-items: center; justify-content: center; }
.day.selected { background: var(--brand-strong); color: #fff; border-color: var(--brand-strong); }
</style>
