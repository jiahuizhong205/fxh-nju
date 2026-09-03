<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Icon from '../components/Icon.vue'
import { fetchJobs, type Job } from '../api/client'

const jobs = ref<Job[]>([])
const favIds = ref<string[]>([])

const tab = ref('全职校招')
const tabs = ['全职校招', '实习探索', '自由自学']

onMounted(async () => {
  jobs.value = await fetchJobs()
})

function isFav(id: string) {
  return favIds.value.includes(id)
}
function toggleFav(id: string) {
  const i = favIds.value.indexOf(id)
  if (i >= 0) favIds.value.splice(i, 1)
  else favIds.value.push(id)
}
function jobTags(j: Job): string[] {
  return [...j.skills_required, ...j.skills_preferred]
}
</script>

<template>
  <div class="career">
    <header class="head">
      <div class="head-top">
        <h2>福小禾 · 职芽探测器 🍀</h2>
        <span class="new-badge">3条新岗</span>
      </div>
      <p class="sub">精准捕获"XX专业+辅修背景优先"的隐藏好岗 🔍</p>
    </header>

    <section class="tabs">
      <button v-for="t in tabs" :key="t" class="tab" :class="{ on: tab === t }" @click="tab = t">{{ t }}</button>
    </section>

    <section class="filters">
      <button class="filter">地点：南京 ▾</button>
      <button class="filter">方向：媒介融合 ▾</button>
      <button class="filter">薪资 ▾</button>
    </section>

    <section class="job-list">
      <div v-for="j in jobs" :key="j.id" class="job" @click="$router.push('/job/' + j.id)">
        <div class="job-head">
          <div>
            <div class="job-company">🌿 {{ j.employer }}</div>
            <div class="job-title">{{ j.title }}</div>
          </div>
          <button class="fav" :class="{ on: isFav(j.id) }" @click.stop="toggleFav(j.id)">
            <Icon name="bookmark-leaf" :size="20" :color="isFav(j.id) ? '#5A7A6B' : undefined" />
          </button>
        </div>
        <div class="match">{{ j.location }} · {{ j.preferred_cross.join(' / ') }} · 截止 {{ j.deadline }}</div>
        <div class="tags">
          <span v-for="t in jobTags(j)" :key="t" class="tag">{{ t }}</span>
        </div>
        <div class="job-actions">
          <button class="action" @click.stop="toggleFav(j.id)">收藏</button>
          <button class="action primary" @click.stop="$router.push('/job/' + j.id)">查看 JD</button>
        </div>
      </div>
    </section>

    <button class="btn-resume">🛠️ 生成我的专属复合简历模板</button>
  </div>
</template>

<style scoped>
.career { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.head-top { display: flex; justify-content: space-between; align-items: center; }
.head-top h2 { font-size: var(--text-xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.new-badge { padding: 2px var(--space-2); background: var(--bg-pink-soft); color: var(--accent-purple); border-radius: var(--radius-full); font-size: var(--text-2xs); font-weight: var(--weight-semibold); }
.sub { margin-top: var(--space-1); font-size: var(--text-xs); color: var(--text-muted); }

.tabs { display: flex; gap: var(--space-2); }
.tab { flex: 1; padding: var(--space-2); border: 1px solid var(--border); background: var(--bg-surface); border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.tab.on { background: var(--brand-strong); color: #fff; border-color: var(--brand-strong); }

.filters { display: flex; gap: var(--space-2); }
.filter { padding: var(--space-2) var(--space-3); border: 1px solid var(--border); background: var(--bg-surface); border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }

.job-list { display: flex; flex-direction: column; gap: var(--space-3); }
.job { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); cursor: pointer; }
.job-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }
.job-company { font-size: var(--text-sm); color: var(--text-secondary); }
.job-title { margin-top: 2px; font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.fav { border: none; background: none; color: var(--text-muted); cursor: pointer; padding: var(--space-1); flex-shrink: 0; }
.fav.on { color: var(--brand-strong); }
.stars { font-size: var(--text-xs); }
.match { font-size: var(--text-sm); color: var(--brand-strong); font-weight: var(--weight-semibold); }
.tags { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.tag { padding: 2px var(--space-2); background: var(--bg-green-faint); color: var(--brand-strong); border-radius: var(--radius-sm); font-size: var(--text-2xs); }
.job-actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.action { flex: 1; padding: var(--space-2); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.action.primary { background: var(--brand-strong); color: #fff; border-color: var(--brand-strong); }

.btn-resume { width: 100%; padding: var(--space-3); border: 1px dashed var(--brand); background: var(--bg-green-faint); color: var(--brand-strong); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: var(--weight-semibold); cursor: pointer; font-family: inherit; }
</style>
