<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '../components/Icon.vue'
import { fetchJob, getFavoriteJobIds, saveFavoriteJobIds, type Job } from '../api/client'

const route = useRoute()
const job = ref<Job | null>(null)
const favorited = ref(false)
const error = ref('')
const today = new Date().toISOString().slice(0, 10)
const sourceUrl = computed(() => job.value?.source?.startsWith('http') ? job.value.source : '')
const expired = computed(() => Boolean(job.value?.deadline && job.value.deadline < today))

onMounted(async () => {
  try {
    job.value = await fetchJob(route.params.id as string)
    favorited.value = getFavoriteJobIds().includes(job.value.id)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '岗位详情加载失败，请稍后重试。'
  }
})

function toggleFavorite() {
  if (!job.value) return
  favorited.value = !favorited.value
  const ids = getFavoriteJobIds().filter(id => id !== job.value?.id)
  if (favorited.value) ids.push(job.value.id)
  saveFavoriteJobIds(ids)
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/career" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>岗位详情</h2>
    </header>

    <template v-if="job">
      <section class="card job-head">
        <div class="job-title-row">
          <div>
            <h3>{{ job.title }}</h3>
            <p class="company">{{ job.employer }}</p>
          </div>
          <button class="fav" :class="{ on: favorited }" @click="toggleFavorite">
            <Icon name="bookmark-leaf" :size="22" :color="favorited ? '#5A7A6B' : undefined" />
          </button>
        </div>
        <div class="chips">
          <span v-for="m in job.majors" :key="m" class="chip selected">{{ m }}</span>
          <span v-for="c in job.preferred_cross" :key="c" class="chip selected">{{ c }}</span>
        </div>
        <div class="meta-line">{{ job.location }} · {{ expired ? '已截止' : '截止' }} {{ job.deadline }} · {{ job.source }}</div>
      </section>

      <section class="card">
        <h4 class="card-title">岗位要求</h4>
        <ul class="list">
          <li v-for="e in job.skills_required" :key="e">{{ e }}</li>
        </ul>
      </section>

      <section class="card">
        <h4 class="card-title">加分项</h4>
        <ul class="list">
          <li v-for="e in job.skills_preferred" :key="e">{{ e }}</li>
        </ul>
      </section>

      <section class="card">
        <h4 class="card-title">投递信息</h4>
        <p class="apply">截止日期：{{ job.deadline }}</p>
        <p class="apply">来源：{{ job.source }}</p>
      </section>

      <div class="actions">
        <button class="btn-ghost" @click="toggleFavorite">{{ favorited ? '取消收藏' : '收藏' }}</button>
        <a v-if="sourceUrl && !expired" class="btn-primary apply-link" :href="sourceUrl" target="_blank" rel="noopener">前往投递</a>
        <button v-else class="btn-primary" disabled>暂无在线投递链接</button>
      </div>
    </template>

    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else class="loading">加载中…</div>
  </div>
</template>

<style scoped>
.job-head h3 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.job-title-row { display: flex; justify-content: space-between; align-items: flex-start; }
.fav { border: none; background: none; color: var(--text-muted); cursor: pointer; padding: var(--space-1); }
.fav.on { color: var(--brand-strong); }
.company { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--text-secondary); }
.chips { margin-top: var(--space-3); display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chips .chip { cursor: default; }
.meta-line { margin-top: var(--space-3); font-size: var(--text-xs); color: var(--text-muted); }

.list { list-style: none; display: flex; flex-direction: column; gap: var(--space-2); }
.list li { position: relative; padding-left: var(--space-4); font-size: var(--text-base); color: var(--text-secondary); line-height: 1.6; }
.list li::before { content: ''; position: absolute; left: 0; top: 9px; width: 6px; height: 6px; border-radius: 50%; background: var(--brand); }

.apply { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.actions { display: flex; gap: var(--space-3); }
.btn-ghost { flex: 1; padding: var(--space-3); border: 1px solid var(--brand-strong); background: #fff; color: var(--brand-strong); border-radius: var(--radius-md); font-size: var(--text-base); font-weight: var(--weight-semibold); cursor: pointer; font-family: inherit; }
.apply-link { flex: 1; text-align: center; text-decoration: none; }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }
.empty { text-align: center; padding: var(--space-8) 0; color: var(--text-muted); }

.loading { text-align: center; padding: 40px 0; color: var(--text-muted); }
</style>
