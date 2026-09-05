<script setup lang="ts">
import { ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const jobTypes = ref<string[]>(['实习岗位'])
const types = [
  { label: '实习岗位', icon: '💼' },
  { label: '校招岗位', icon: '🎓' },
  { label: '项目/课题', icon: '📊' },
  { label: '政府/事业单位', icon: '🏛️' },
  { label: '海外/远程', icon: '🌍' },
]

const cities = ref<string[]>(['南京'])
const cityOptions = ['不限', '南京', '上海', '北京', '深圳', '苏州', '杭州', '远程', '海外']

const industries = ref<string[]>(['文化/传媒'])
const industryOptions = ['互联网/科技', '金融/咨询', '文化/传媒', '教育/学术', '生物/医药', '法律/公共事务', '快消/零售', '新能源/制造', '其他']

function toggle(list: string[], item: string) {
  const i = list.indexOf(item)
  if (i >= 0) list.splice(i, 1)
  else list.push(item)
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>岗位推送偏好</h2>
    </header>

    <p class="page-sub">新花开在哪片地？🌸</p>

    <div class="illus"><img src="/illustrations/dandelion.png" alt="" /></div>

    <section class="card">
      <h4 class="card-title">岗位类型</h4>
      <div class="type-list">
        <button v-for="t in types" :key="t.label" class="type" :class="{ selected: jobTypes.includes(t.label) }" @click="toggle(jobTypes, t.label)">
          <span class="type-icon">{{ t.icon }}</span>
          <span class="type-label">{{ t.label }}</span>
        </button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">📍 你希望在哪里工作？</h4>
      <div class="chips">
        <button v-for="c in cityOptions" :key="c" class="chip" :class="{ selected: cities.includes(c) }" @click="toggle(cities, c)">{{ c }}</button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">🎨 你对哪类工作感兴趣？</h4>
      <div class="chips">
        <button v-for="i in industryOptions" :key="i" class="chip" :class="{ selected: industries.includes(i) }" @click="toggle(industries, i)">{{ i }}</button>
      </div>
    </section>

    <button class="btn-primary">保存岗位偏好 🌿</button>
    <p class="foot">推送岗位将优先匹配你的辅修方向+主修背景，同时符合你的行业偏好 🌸</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100px; height: 80px; }
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.type-list { display: flex; flex-direction: column; gap: var(--space-2); }
.type { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-md); cursor: pointer; font-family: inherit; text-align: left; }
.type.selected { border-color: var(--brand); background: var(--bg-green-faint); }
.type-icon { font-size: var(--text-xl); }
.type-label { font-size: var(--text-sm); color: var(--text-primary); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); line-height: 1.6; }
</style>
