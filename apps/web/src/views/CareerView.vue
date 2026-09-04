<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Icon from '../components/Icon.vue'
import { fetchJobs, getFavoriteJobIds, saveFavoriteJobIds, type Job } from '../api/client'

const jobs = ref<Job[]>([])
const favIds = ref<string[]>([])

const tab = ref('有效岗位')
const tabs = ['全部岗位', '有效岗位', '我的收藏']
const location = ref('')
const keyword = ref('')
const error = ref('')
const today = new Date().toISOString().slice(0, 10)

const locations = computed(() => [...new Set(jobs.value.map(j => j.location).filter(Boolean))])
const activeCount = computed(() => jobs.value.filter(j => !isExpired(j)).length)
const filteredJobs = computed(() => jobs.value.filter(j => {
  if (tab.value === '有效岗位' && isExpired(j)) return false
  if (tab.value === '我的收藏' && !isFav(j.id)) return false
  if (location.value && j.location !== location.value) return false
  if (keyword.value) {
    const text = [j.employer, j.title, ...jobTags(j)].join(' ').toLowerCase()
    if (!text.includes(keyword.value.toLowerCase())) return false
  }
  return true
}))

onMounted(async () => {
  favIds.value = getFavoriteJobIds()
  try {
    jobs.value = await fetchJobs()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '岗位加载失败，请稍后重试。'
  }
})

function isExpired(j: Job) {
  return Boolean(j.deadline && j.deadline < today)
}

function isFav(id: string) {
  return favIds.value.includes(id)
}
function toggleFav(id: string) {
  const i = favIds.value.indexOf(id)
  if (i >= 0) favIds.value.splice(i, 1)
  else favIds.value.push(id)
  saveFavoriteJobIds(favIds.value)
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
        <span class="new-badge">{{ activeCount }}条有效岗位</span>
      </div>
      <p class="sub">精准捕获"XX专业+辅修背景优先"的隐藏好岗 🔍</p>
    </header>

    <section class="tabs">
      <button v-for="t in tabs" :key="t" class="tab" :class="{ on: tab === t }" @click="tab = t">{{ t }}</button>
    </section>

    <section class="filters">
      <select v-model="location" class="filter"><option value="">地点：全部</option><option v-for="l in locations" :key="l" :value="l">地点：{{ l }}</option></select>
      <input v-model="keyword" class="filter keyword" placeholder="搜索岗位或技能" />
    </section>

    <section class="job-list">
      <div v-for="j in filteredJobs" :key="j.id" class="job" :class="{ expired: isExpired(j) }" @click="$router.push('/job/' + j.id)">
        <div class="job-head">
          <div>
            <div class="job-company">🌿 {{ j.employer }}</div>
            <div class="job-title">{{ j.title }}</div>
          </div>
          <button class="fav" :class="{ on: isFav(j.id) }" @click.stop="toggleFav(j.id)">
            <Icon name="bookmark-leaf" :size="20" :color="isFav(j.id) ? '#5A7A6B' : undefined" />
          </button>
        </div>
        <div class="match">{{ j.location }} · {{ j.preferred_cross.join(' / ') }} · <span :class="{ 'expired-text': isExpired(j) }">{{ isExpired(j) ? '已截止' : '截止' }} {{ j.deadline }}</span></div>
        <div class="tags">
          <span v-for="t in jobTags(j)" :key="t" class="tag">{{ t }}</span>
        </div>
        <div class="job-actions">
          <button class="action" @click.stop="toggleFav(j.id)">收藏</button>
          <button class="action primary" @click.stop="$router.push('/job/' + j.id)">查看 JD</button>
        </div>
      </div>
    </section>
    <p v-if="error" class="empty">{{ error }}</p>
    <p v-else-if="!filteredJobs.length" class="empty">当前筛选条件下没有岗位。</p>

    <button class="btn-resume" @click="$router.push('/edit-profile')">🛠️ 完善画像，为简历生成做准备</button>
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
.filter { min-width: 0; flex: 1; padding: var(--space-2) var(--space-3); border: 1px solid var(--border); background: var(--bg-surface); border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.keyword { outline: none; }

.job-list { display: flex; flex-direction: column; gap: var(--space-3); }
.job { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); cursor: pointer; }
.job.expired { opacity: 0.7; }
.job-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }
.job-company { font-size: var(--text-sm); color: var(--text-secondary); }
.job-title { margin-top: 2px; font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.fav { border: none; background: none; color: var(--text-muted); cursor: pointer; padding: var(--space-1); flex-shrink: 0; }
.fav.on { color: var(--brand-strong); }
.stars { font-size: var(--text-xs); }
.match { font-size: var(--text-sm); color: var(--brand-strong); font-weight: var(--weight-semibold); }
.expired-text { color: var(--text-muted); }
.tags { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.tag { padding: 2px var(--space-2); background: var(--bg-green-faint); color: var(--brand-strong); border-radius: var(--radius-sm); font-size: var(--text-2xs); }
.job-actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.action { flex: 1; padding: var(--space-2); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.action.primary { background: var(--brand-strong); color: #fff; border-color: var(--brand-strong); }

.btn-resume { width: 100%; padding: var(--space-3); border: 1px dashed var(--brand); background: var(--bg-green-faint); color: var(--brand-strong); border-radius: var(--radius-md); font-size: var(--text-sm); font-weight: var(--weight-semibold); cursor: pointer; font-family: inherit; }
.empty { text-align: center; color: var(--text-muted); font-size: var(--text-sm); padding: var(--space-4); }
</style>
