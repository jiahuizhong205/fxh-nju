<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, recommendPrograms, type Recommendation, type StudentProfile } from '../api/client'
import BackButton from '../components/BackButton.vue'

const router = useRouter()
const profile = ref<StudentProfile | null>(null)
const recommendations = ref<Recommendation[]>([])
const loading = ref(false)
const error = ref('')

const scoreKeys = ['interest_fit', 'career_fit', 'prerequisite_readiness', 'schedule_feasibility', 'campus_feasibility']
const scoreLabel: Record<string, string> = {
  interest_fit: '兴趣匹配', career_fit: '职业匹配', prerequisite_readiness: '先修准备',
  schedule_feasibility: '排课可行', campus_feasibility: '校区可行',
}

const hasProfile = computed(() => !!profile.value)
const profileInterests = computed(() => profile.value?.interests?.slice(0, 3).join(' · ') || '待补充')
const profileStrengths = computed(() => profile.value?.strengths?.slice(0, 3).join(' · ') || '待补充')

onMounted(async () => {
  try {
    profile.value = await fetchProfile()
    if (profile.value) await getRecommendation()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '画像加载失败，请稍后重试。'
  }
})

async function getRecommendation() {
  loading.value = true
  error.value = ''
  try {
    recommendations.value = await recommendPrograms()
    if (!recommendations.value.length) error.value = '当前没有可用的推荐结果。'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '推荐生成失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function matchFlowers(score: number) {
  return '🌼'.repeat(Math.max(1, Math.min(5, Math.round(score * 5))))
}

</script>

<template>
  <div class="recommend-page">
    <header class="page-head">
      <BackButton fallback="/" />
      <div>
        <h2>复合花粉匹配 🍃</h2>
        <p>寻找最适合你的学科土壤</p>
      </div>
    </header>

    <section v-if="!hasProfile" class="card empty-state">
      <p>尚未填写学生画像，推荐无法进行。</p>
      <router-link to="/edit-profile" class="link-btn">去填写画像</router-link>
    </section>

    <template v-else>
      <section class="card soil-card">
        <div class="section-title"><span>🌱</span><h3>我的学科土壤</h3></div>
        <div class="soil-line"><span>主修专业</span><strong>{{ profile?.major || '待补充' }}</strong></div>
        <div class="soil-line"><span>偏好兴趣</span><strong>{{ profileInterests }}</strong></div>
        <div class="soil-line"><span>核心特长</span><strong>{{ profileStrengths }}</strong></div>
        <router-link to="/edit-profile" class="edit-profile">编辑画像 ›</router-link>
      </section>

      <section class="prompt-card">
        <div class="prompt-icon">🔔</div>
        <div class="prompt-copy">
          <strong>小禾提问：你通过高等数学(A)了吗？</strong>
          <span>补充先修情况，推荐会更准确</span>
        </div>
        <router-link to="/edit-profile" class="prompt-action">去确认</router-link>
      </section>

      <button class="btn-recommend" :disabled="loading" @click="getRecommendation">
        {{ loading ? '正在生成推荐...' : recommendations.length ? '重新生成推荐' : '生成辅修推荐' }}
      </button>
      <p v-if="error" class="error-msg">{{ error }}</p>

      <section v-if="recommendations.length" class="rec-list">
        <article v-for="(r, i) in recommendations" :key="r.program.name" class="rec-card">
          <div class="rec-head">
            <div>
              <span class="rec-index">推荐 {{ i + 1 }}</span>
              <h3>{{ r.program.name }}辅修</h3>
            </div>
            <span class="rec-score">{{ (r.total_score * 100).toFixed(0) }}%</span>
          </div>
          <p class="rec-meta">{{ r.program.discipline }} · {{ r.program.campus }} · {{ r.program.total_credits }} 学分</p>
          <p class="match-line">{{ matchFlowers(r.total_score) }} <span>综合匹配度</span></p>

          <div class="rec-scores">
            <div v-for="k in scoreKeys" :key="k" class="score-row">
              <span>{{ scoreLabel[k] }}</span>
              <strong>{{ ((r.scores[k] ?? 0) * 100).toFixed(0) }}%</strong>
            </div>
          </div>

          <p class="rec-courses"><span>核心课程</span>{{ r.program.core_courses.slice(0, 4).join('、') }}</p>
          <p v-if="r.risks.length" class="rec-risks">⚠ {{ r.risks.join('；') }}</p>
          <router-link v-if="i === 0" to="/minor-report" class="report-link">查看详细分析报告 ›</router-link>
        </article>
      </section>

      <p v-else-if="!loading" class="empty-result">点击上方按钮，生成属于你的复合方向。</p>

      <router-link v-if="recommendations.length" to="/course-planning" class="btn-primary cta">🌱 种下这颗种子，开启培养计划</router-link>
    </template>
  </div>
</template>

<style scoped>
.recommend-page { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.page-head { display: flex; align-items: center; gap: var(--space-3); }
.back { width: 40px; height: 40px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border: 1px solid var(--bg-green-soft); border-radius: var(--radius-full); background: var(--bg-surface); color: var(--brand-strong); cursor: pointer; }
.page-head h2 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.page-head p { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--text-secondary); }

.card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-4); }
.soil-card { display: flex; flex-direction: column; gap: var(--space-3); }
.section-title { display: flex; align-items: center; gap: var(--space-2); color: var(--accent-purple); }
.section-title h3 { font-size: var(--text-lg); font-weight: var(--weight-semibold); }
.soil-line { display: flex; align-items: baseline; gap: var(--space-3); font-size: var(--text-sm); }
.soil-line span { min-width: 64px; color: var(--text-muted); }
.soil-line strong { color: var(--text-primary); font-weight: var(--weight-semibold); }
.edit-profile { align-self: flex-end; color: var(--brand-strong); font-size: var(--text-xs); text-decoration: none; }

.prompt-card { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--accent-purple-soft); border-radius: var(--radius-md); background: #fbf8fc; }
.prompt-icon { font-size: var(--text-xl); }
.prompt-copy { display: flex; flex: 1; min-width: 0; flex-direction: column; gap: 2px; }
.prompt-copy strong { color: var(--accent-purple); font-size: var(--text-sm); }
.prompt-copy span { color: var(--text-muted); font-size: var(--text-xs); }
.prompt-action { color: var(--accent-purple); font-size: var(--text-xs); font-weight: var(--weight-semibold); text-decoration: none; white-space: nowrap; }

.btn-recommend { width: 100%; padding: var(--space-3); border: 0; border-radius: var(--radius-md); background: var(--brand-strong); color: #fff; font-size: var(--text-base); font-weight: var(--weight-semibold); cursor: pointer; font-family: inherit; }
.btn-recommend:disabled { background: var(--bg-green-soft); cursor: not-allowed; }
.error-msg { color: var(--accent-purple); font-size: var(--text-sm); }

.rec-list { display: flex; flex-direction: column; gap: var(--space-3); }
.rec-card { padding: var(--space-4); background: var(--bg-surface); border: 1px solid var(--bg-green-soft); border-radius: var(--radius-lg); box-shadow: 0 4px 12px rgba(47, 59, 53, 0.04); }
.rec-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }
.rec-index { display: inline-block; padding: 2px var(--space-2); border-radius: var(--radius-full); background: var(--bg-green-faint); color: var(--brand-strong); font-size: var(--text-2xs); }
.rec-head h3 { margin-top: var(--space-2); font-size: var(--text-lg); font-weight: var(--weight-bold); color: var(--text-primary); }
.rec-score { color: var(--brand-strong); font-size: var(--text-2xl); font-weight: var(--weight-bold); }
.rec-meta { margin-top: var(--space-2); color: var(--text-muted); font-size: var(--text-xs); }
.match-line { margin-top: var(--space-3); color: var(--brand); font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.match-line span { margin-left: var(--space-2); color: var(--brand-strong); }
.rec-scores { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2) var(--space-4); margin-top: var(--space-4); padding: var(--space-3) 0; border-top: 1px solid var(--bg-subtle); border-bottom: 1px solid var(--bg-subtle); }
.score-row { display: flex; justify-content: space-between; gap: var(--space-2); color: var(--text-secondary); font-size: var(--text-xs); }
.score-row strong { color: var(--brand-strong); font-weight: var(--weight-semibold); }
.rec-courses { display: flex; gap: var(--space-2); margin-top: var(--space-3); color: var(--text-secondary); font-size: var(--text-xs); line-height: 1.6; }
.rec-courses span { flex-shrink: 0; color: var(--text-muted); }
.rec-risks { margin-top: var(--space-2); color: var(--accent-purple); font-size: var(--text-xs); line-height: 1.5; }
.report-link { display: inline-block; margin-top: var(--space-3); color: var(--brand-strong); font-size: var(--text-sm); font-weight: var(--weight-semibold); text-decoration: none; }
.empty-state, .empty-result { text-align: center; color: var(--text-muted); }
.empty-state { padding: var(--space-8) var(--space-4); }
.link-btn { display: inline-block; margin-top: var(--space-3); padding: var(--space-2) var(--space-5); background: var(--brand-strong); color: #fff; border-radius: var(--radius-md); text-decoration: none; font-size: var(--text-sm); }
.empty-result { padding: var(--space-4); font-size: var(--text-sm); }
.cta { display: block; text-align: center; text-decoration: none; }

@media (max-width: 390px) {
  .soil-line { align-items: flex-start; flex-direction: column; gap: 2px; }
  .soil-line span { min-width: 0; }
  .rec-scores { grid-template-columns: 1fr; }
}
</style>
