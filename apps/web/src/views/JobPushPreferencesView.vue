<script setup lang="ts">
import { ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const jobTypes = ref<string[]>(['实习岗位'])
const types = [
  { label: '实习岗位', icon: '💼', desc: '适合在校生的日常/暑期实习' },
  { label: '校招岗位', icon: '🎓', desc: '应届生全职招聘' },
  { label: '项目/课题', icon: '📊', desc: '科研助理、课题组招募' },
  { label: '政府/事业单位', icon: '🏛️', desc: '智库、政策研究等公职方向' },
  { label: '海外/远程', icon: '🌍', desc: '可远程或海外机会' },
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

    <section class="card type-card">
      <h4 class="card-title">岗位类型</h4>
      <div class="type-list">
        <template v-for="(t, index) in types" :key="t.label">
          <button class="type" :class="{ selected: jobTypes.includes(t.label) }" @click="toggle(jobTypes, t.label)">
            <span class="type-icon">{{ t.icon }}</span>
            <span class="type-copy">
              <span class="type-label">{{ t.label }}</span>
              <span class="type-desc">{{ t.desc }}</span>
            </span>
            <span class="toggle-indicator" :class="{ on: jobTypes.includes(t.label) }"><span /></span>
          </button>
          <div v-if="index < types.length - 1" class="type-divider" aria-hidden="true" />
        </template>
      </div>
    </section>

    <section class="card preference-card">
      <h4 class="card-title">📍 你希望在哪里工作？</h4>
      <div class="chips">
        <button v-for="c in cityOptions" :key="c" class="chip" :class="{ selected: cities.includes(c) }" @click="toggle(cities, c)">{{ c }}</button>
      </div>
      <div class="preference-divider" />
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
.type-card, .preference-card { border-color: var(--bg-green-soft); }
.type-list { display: flex; flex-direction: column; gap: var(--space-2); }
.type { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) 0; border: none; background: transparent; cursor: pointer; font-family: inherit; text-align: left; }
.type-divider { height: 1px; background: var(--bg-green-soft); }
.type.selected { border-color: transparent; background: transparent; }
.type-icon { width: 32px; font-size: var(--text-xl); text-align: center; flex-shrink: 0; }
.type-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.type-label { font-size: var(--text-sm); color: var(--text-primary); }
.type-desc { font-size: var(--text-xs); color: var(--text-muted); }
.toggle-indicator { width: 44px; height: 26px; position: relative; flex-shrink: 0; border-radius: var(--radius-full); background: var(--bg-green-soft); }
.toggle-indicator span { position: absolute; top: 3px; left: 3px; width: 20px; height: 20px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.12); transition: left .2s; }
.toggle-indicator.on { background: var(--brand); }
.toggle-indicator.on span { left: 21px; }
.preference-divider { height: 1px; margin: var(--space-4) 0; background: var(--bg-green-soft); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); line-height: 1.6; }
</style>
