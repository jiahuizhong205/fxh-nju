<script setup lang="ts">
import { ref } from 'vue'

const scope = ref('仅自己')
const scopes = [
  { name: '仅自己', desc: '只有自己能查看学习进度和辅修规划' },
  { name: '仅好友', desc: '已互关的好友可查看你的学习进度' },
  { name: '同专业同学', desc: '同一主修专业的同学可查看你的表现' },
  { name: '全校公开', desc: '南京大学全体学生可查看你的可见花园' },
]

const showCourse = ref(true)
const showGrade = ref(false)
const showTimetable = ref(true)
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/profile" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>学习进度可见范围</h2>
    </header>

    <p class="page-sub">谁可以看我的花园</p>

    <div class="illus"><img src="/illustrations/fence-garden.png" alt="" /></div>

    <section class="card" style="padding: 0; overflow: hidden;">
      <div v-for="s in scopes" :key="s.name" class="scope" @click="scope = s.name">
        <div class="scope-main">
          <div class="scope-name">{{ s.name }}</div>
          <div class="scope-desc">{{ s.desc }}</div>
        </div>
        <span class="radio" :class="{ on: scope === s.name }"></span>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">详细展示范围</h4>
      <div class="row">
        <div class="row-label">是否显示具体课程名称？</div>
        <div class="toggle" :class="{ on: showCourse }" @click="showCourse = !showCourse"><div class="knob"></div></div>
      </div>
      <div class="row">
        <div class="row-label">是否显示成绩/绩点？</div>
        <div class="toggle" :class="{ on: showGrade }" @click="showGrade = !showGrade"><div class="knob"></div></div>
      </div>
      <div class="row">
        <div class="row-label">是否显示课表时间？</div>
        <div class="toggle" :class="{ on: showTimetable }" @click="showTimetable = !showTimetable"><div class="knob"></div></div>
      </div>
    </section>

    <button class="btn-primary">保存可见范围</button>
    <p class="foot">你的姓名和联系方式始终不会对外公开 🌿</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 129px; height: 80px; }
.scope { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--bg-subtle); cursor: pointer; }
.scope:last-child { border-bottom: none; }
.scope-name { font-size: var(--text-base); font-weight: var(--weight-medium); color: var(--text-primary); }
.scope-desc { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.radio { width: 20px; height: 20px; border-radius: 50%; border: 2px solid var(--border); flex-shrink: 0; }
.radio.on { border-color: var(--brand); background: var(--brand); box-shadow: inset 0 0 0 4px var(--bg-surface); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-2); }
.row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; }
.row-label { font-size: var(--text-sm); color: var(--text-primary); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
