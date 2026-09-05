<script setup lang="ts">
import { ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const scope = ref('仅自己')
const scopes = [
  { name: '仅自己', desc: '只有自己能查看学习进度和辅修规划', tone: 'self' },
  { name: '仅好友', desc: '已互关的好友可查看你的学习进度', tone: 'friends' },
  { name: '同专业同学', desc: '同一主修专业的同学可查看你的表现', tone: 'major' },
  { name: '全校公开', desc: '南京大学全体学生可查看你的可见花园', tone: 'public' },
]

const showCourse = ref(true)
const showGrade = ref(false)
const showTimetable = ref(true)
const saved = ref(false)

function save() {
  saved.value = true
}
</script>

<template>
  <div class="page visibility-page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <h2>学习进度可见范围</h2>
    </header>

    <p class="page-sub">谁可以看我的花园</p>

    <div class="illus"><img src="/illustrations/fence-garden.png" alt="四种学习进度可见范围" /></div>

    <section class="scope-list" aria-label="学习进度可见范围">
      <button v-for="s in scopes" :key="s.name" type="button" class="scope" :class="{ selected: scope === s.name }" @click="scope = s.name; saved = false">
        <span class="scope-icon" :class="[`scope-icon-${s.tone}`, { selected: scope === s.name }]" aria-hidden="true">
          <svg v-if="s.tone === 'self'" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></svg>
          <svg v-else-if="s.tone === 'friends'" viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="9" r="3" /><circle cx="16" cy="10" r="2.5" /><path d="M3.5 19c.5-3 2.3-4.5 5.5-4.5s5 1.5 5.5 4.5M14 15.5c2.9-.2 4.9.9 5.5 3.5" /></svg>
          <svg v-else-if="s.tone === 'major'" viewBox="0 0 24 24" aria-hidden="true"><path d="m3 9 9-4 9 4-9 4-9-4Z" /><path d="M7 11v4c2.6 2.2 7.4 2.2 10 0v-4M21 9v6" /></svg>
          <svg v-else viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c2.2 2.4 3.3 5.4 3.3 9s-1.1 6.6-3.3 9c-2.2-2.4-3.3-5.4-3.3-9S9.8 5.4 12 3Z" /></svg>
        </span>
        <div class="scope-main">
          <div class="scope-name">{{ s.name }}</div>
          <div class="scope-desc">{{ s.desc }}</div>
        </div>
        <span v-if="scope === s.name" class="scope-mark" aria-hidden="true">🌸</span>
      </button>
    </section>

    <section class="detail-section">
      <h4 class="card-title">详细展示范围</h4>
      <button type="button" class="row" :aria-pressed="showCourse" @click="showCourse = !showCourse; saved = false">
        <div class="row-label">是否显示具体课程名称？</div>
        <span class="toggle" :class="{ on: showCourse }" aria-hidden="true"><span class="knob"></span></span>
      </button>
      <button type="button" class="row" :aria-pressed="showGrade" @click="showGrade = !showGrade; saved = false">
        <div class="row-label">是否显示成绩/绩点？</div>
        <span class="toggle" :class="{ on: showGrade }" aria-hidden="true"><span class="knob"></span></span>
      </button>
      <button type="button" class="row" :aria-pressed="showTimetable" @click="showTimetable = !showTimetable; saved = false">
        <div class="row-label">是否显示课表时间？</div>
        <span class="toggle" :class="{ on: showTimetable }" aria-hidden="true"><span class="knob"></span></span>
      </button>
    </section>

    <button class="btn-primary" @click="save">{{ saved ? '已保存可见范围' : '🍃 保存可见范围' }}</button>
    <p class="foot">你的姓名和联系方式始终不会对外公开 🌿</p>
  </div>
</template>

<style scoped>
.visibility-page { gap: var(--space-4); padding: var(--space-4) var(--space-5) var(--space-5); }
.visibility-page .page-head { position: relative; justify-content: center; }
.visibility-page .page-head .back { position: absolute; left: 0; }
.visibility-page .page-head h2 { font-size: var(--text-2xl); }
.visibility-page .page-sub { margin: calc(var(--space-1) * -1) 0 0; color: var(--text-muted); font-size: var(--text-md); }
.illus { display: flex; justify-content: center; margin: var(--space-1) 0; }
.illus img { width: 129px; height: 80px; object-fit: contain; }
.scope-list { display: flex; flex-direction: column; gap: var(--space-4); }
.scope { display: flex; align-items: center; gap: var(--space-3); width: 100%; padding: var(--space-4); border: 2px solid transparent; border-radius: var(--radius-2xl); background: var(--bg-surface); box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); color: inherit; cursor: pointer; font: inherit; text-align: left; }
.scope.selected { border-color: var(--accent-purple); }
.scope-icon { width: 50px; height: 50px; display: grid; place-items: center; flex-shrink: 0; border-radius: var(--radius-full); }
.scope-icon svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.scope-icon-self { background: #626262; color: #fff; }
.scope-icon-friends { background: #e8f3df; color: var(--brand); }
.scope-icon-major { background: #eee9f4; color: var(--accent-purple); }
.scope-icon-public { background: #fbe5df; color: #d88174; }
.scope-main { flex: 1; min-width: 0; }
.scope-name { font-size: var(--text-lg); font-weight: var(--weight-semibold); color: var(--text-primary); }
.scope-desc { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.scope-mark { flex-shrink: 0; color: #edc8be; font-size: var(--text-xl); }

.detail-section { padding-top: var(--space-1); }
.card-title { font-size: var(--text-md); font-weight: var(--weight-semibold); color: var(--accent-purple); margin-bottom: var(--space-3); }
.row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); width: 100%; padding: var(--space-3) 0; border: none; background: transparent; color: inherit; cursor: pointer; font: inherit; text-align: left; }
.row-label { font-size: var(--text-sm); color: var(--text-primary); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
