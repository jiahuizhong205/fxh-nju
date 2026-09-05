<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import Icon from '../components/Icon.vue'
import { fetchJob, getFavoriteJobIds, saveFavoriteJobIds, type Job } from '../api/client'
import BackButton from '../components/BackButton.vue'

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
  <div class="page job-detail-page">
    <header class="page-head">
      <BackButton fallback="/career" />
      <div>
        <h2>岗位详情 🌱</h2>
        <p>找到适合你生长的机会</p>
      </div>
    </header>

    <template v-if="job">
      <section class="card job-summary">
        <div class="employer-row">
          <span class="employer-icon" aria-hidden="true">▥</span>
          <strong>{{ job.employer }}</strong>
          <span class="source-tag">{{ job.source }}</span>
        </div>
        <div class="job-title-row">
          <div>
            <h3>{{ job.title }}</h3>
          </div>
          <button class="fav" :class="{ on: favorited }" @click="toggleFavorite">
            <Icon name="bookmark-leaf" :size="22" :color="favorited ? '#5A7A6B' : undefined" />
          </button>
        </div>
        <div class="match-pill"><span>♧</span>岗位匹配标签</div>
        <div class="chips">
          <span v-for="m in job.majors" :key="m" class="chip selected">{{ m }}</span>
          <span v-for="c in job.preferred_cross" :key="c" class="chip selected">{{ c }}</span>
        </div>
      </section>

      <section class="card detail-list">
        <div class="detail-row">
          <span class="detail-icon green" aria-hidden="true">⌖</span>
          <div><small>工作地点</small><strong>{{ job.location || '暂未标注' }}</strong></div>
        </div>
        <div class="detail-row">
          <span class="detail-icon purple" aria-hidden="true">⌂</span>
          <div><small>岗位类型</small><strong>{{ job.preferred_cross.join(' / ') || '暂未标注' }}</strong></div>
        </div>
        <div class="detail-row">
          <span class="detail-icon orange" aria-hidden="true">◷</span>
          <div><small>{{ expired ? '截止状态' : '截止时间' }}</small><strong>{{ expired ? '已截止' : job.deadline || '暂未标注' }}</strong></div>
        </div>
        <div class="detail-row">
          <span class="detail-icon blue" aria-hidden="true">▣</span>
          <div><small>岗位来源</small><strong>{{ job.source || '暂未标注' }}</strong></div>
        </div>
      </section>

      <section v-if="job.skills_required.length" class="card requirement-card">
        <h4 class="card-title">🍃 我们希望你</h4>
        <ul class="list">
          <li v-for="e in job.skills_required" :key="e">{{ e }}</li>
        </ul>
      </section>

      <section v-if="job.skills_preferred.length" class="card requirement-card">
        <h4 class="card-title">🪻 加分项</h4>
        <ul class="list">
          <li v-for="e in job.skills_preferred" :key="e">{{ e }}</li>
        </ul>
      </section>

      <section class="card apply-card">
        <h4 class="card-title">▣ 如何投递</h4>
        <p class="apply">投递方式：{{ sourceUrl ? '点击下方按钮进入岗位来源页面' : '当前岗位暂未提供在线投递链接' }}</p>
        <p class="apply"><strong>{{ expired ? '截止状态：' : '截止日期：' }}</strong>{{ job.deadline || '暂未标注' }}</p>
        <p class="apply"><strong>来源：</strong>{{ job.source || '暂未标注' }}</p>
      </section>

      <div class="actions">
        <button class="btn-ghost" @click="toggleFavorite">{{ favorited ? '已收藏' : '收藏' }}</button>
        <a v-if="sourceUrl && !expired" class="btn-primary apply-link" :href="sourceUrl" target="_blank" rel="noopener">立即投递</a>
        <button v-else class="btn-primary" disabled>{{ expired ? '岗位已截止' : '暂无在线投递链接' }}</button>
      </div>
    </template>

    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else class="loading">加载中…</div>
  </div>
</template>

<style scoped>
.job-detail-page { gap: var(--space-4); padding-top: var(--space-5); }
.page-head h2 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.page-head p { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--brand-strong); }
.card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-xl); padding: var(--space-4); }
.job-summary { border-color: var(--bg-green-soft); box-shadow: 0 4px 14px rgba(47, 59, 53, 0.04); }
.employer-row { display: flex; align-items: center; gap: var(--space-2); color: var(--text-secondary); font-size: var(--text-sm); }
.employer-icon { color: var(--accent-purple); font-size: var(--text-lg); }
.source-tag { margin-left: auto; padding: 4px var(--space-2); border-radius: var(--radius-full); background: var(--bg-green-faint); color: var(--brand-strong); font-size: var(--text-2xs); }
.job-title-row { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); margin-top: var(--space-4); }
.job-title-row h3 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.fav { border: none; background: none; color: var(--text-muted); cursor: pointer; padding: var(--space-1); }
.fav.on { color: var(--brand-strong); }
.match-pill { display: inline-flex; align-items: center; gap: var(--space-2); margin-top: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-full); background: var(--accent-purple-soft); color: var(--accent-purple); font-size: var(--text-sm); }
.match-pill span { font-size: var(--text-lg); }
.chips { margin-top: var(--space-3); display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chips .chip { cursor: default; }
.detail-list { display: flex; flex-direction: column; gap: 0; }
.detail-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--bg-subtle); }
.detail-row:last-child { border-bottom: none; }
.detail-icon { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; border-radius: var(--radius-full); font-size: var(--text-lg); }
.detail-icon.green { background: var(--bg-green-faint); color: var(--brand-strong); }
.detail-icon.purple { background: var(--accent-purple-soft); color: var(--accent-purple); }
.detail-icon.orange { background: #fff4e8; color: #c77b22; }
.detail-icon.blue { background: #e6f3fb; color: #2785bd; }
.detail-row div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.detail-row small { color: var(--text-muted); font-size: var(--text-xs); }
.detail-row strong { color: var(--text-primary); font-size: var(--text-sm); }
.card-title { margin-bottom: var(--space-3); font-size: var(--text-lg); font-weight: var(--weight-semibold); color: var(--text-primary); }
.list { list-style: none; display: flex; flex-direction: column; gap: var(--space-2); }
.list li { position: relative; padding-left: var(--space-4); font-size: var(--text-base); color: var(--text-secondary); line-height: 1.6; }
.list li::before { content: '✦'; position: absolute; left: 0; color: var(--brand); }
.apply-card { border-color: var(--brand); background: var(--bg-green-faint); }
.apply { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }
.apply + .apply { margin-top: var(--space-2); }
.apply strong { color: var(--text-primary); }
.actions { position: sticky; bottom: 0; display: flex; gap: var(--space-3); padding: var(--space-3) 0 var(--space-2); background: linear-gradient(180deg, transparent, var(--bg-page) 24%); }
.btn-ghost { flex: 0 0 92px; padding: var(--space-3); border: 1px solid var(--brand); background: var(--bg-surface); color: var(--brand-strong); border-radius: var(--radius-full); font-size: var(--text-sm); font-weight: var(--weight-semibold); cursor: pointer; font-family: inherit; }
.apply-link, .actions > .btn-primary { flex: 1; text-align: center; text-decoration: none; }
.btn-primary:disabled { opacity: 0.55; cursor: not-allowed; }
.empty { text-align: center; padding: var(--space-8) 0; color: var(--text-muted); }
.loading { text-align: center; padding: 40px 0; color: var(--text-muted); }
</style>
