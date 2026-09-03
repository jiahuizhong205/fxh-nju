<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchProfile, recommendPrograms, fetchPlan, type Recommendation, type PlanResult, type PlanItem } from '../api/client'

const rec = ref<Recommendation | null>(null)
const plan = ref<PlanResult | null>(null)
const hasProfile = ref(false)

const scoreKeys = ['interest_fit', 'career_fit', 'prerequisite_readiness', 'schedule_feasibility', 'campus_feasibility']
const scoreLabel: Record<string, string> = {
  interest_fit: '兴趣匹配', career_fit: '职业匹配', prerequisite_readiness: '先修准备',
  schedule_feasibility: '排课可行', campus_feasibility: '校区可行',
}
const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八']

onMounted(async () => {
  const p = await fetchProfile()
  hasProfile.value = !!p
  if (!p) return
  const recs = await recommendPrograms()
  if (!recs.length) return
  rec.value = recs[0]
  plan.value = await fetchPlan(recs[0].program.name)
})

function termLabel(it: PlanItem): string {
  return `大${CN_NUM[it.year] ?? it.year}·${it.term}`
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/recommend" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>辅修推荐分析报告</h2>
    </header>

    <div v-if="!hasProfile" class="card empty">
      <p>尚未填写学生画像，无法生成报告。</p>
      <router-link to="/edit-profile" class="link-btn">去填写画像</router-link>
    </div>

    <template v-else-if="rec">
      <section class="card head-card">
        <p class="report-tag">复合花粉匹配 · 辅修分析报告</p>
        <h3>{{ rec.program.name }} · 辅修适配解读</h3>
        <p class="meta">{{ rec.program.discipline }} · 学科评估 {{ rec.program.subject_rank }} · {{ rec.program.campus }}</p>
        <div class="score-row">
          <div class="score">
            <span class="score-k">综合匹配</span>
            <span class="score-v">{{ (rec.total_score * 100).toFixed(0) }}%</span>
          </div>
          <div class="score">
            <span class="score-k">需修学分</span>
            <span class="score-v">{{ rec.program.total_credits }}</span>
          </div>
        </div>
      </section>

      <section class="card">
        <h4 class="card-title">匹配度评分</h4>
        <div class="score-list">
          <div v-for="k in scoreKeys" :key="k" class="score-line">
            <span>{{ scoreLabel[k] }}</span>
            <span>{{ ((rec.scores[k] ?? 0) * 100).toFixed(0) }}%</span>
          </div>
        </div>
      </section>

      <section v-if="rec.risks.length" class="card">
        <h4 class="card-title">风险提示</h4>
        <p v-for="r in rec.risks" :key="r" class="risk">⚠ {{ r }}</p>
      </section>

      <section class="card">
        <h4 class="card-title">核心课程</h4>
        <div class="chip-row">
          <span v-for="c in rec.program.core_courses" :key="c" class="chip">{{ c }}</span>
        </div>
      </section>

      <template v-if="plan">
        <section class="card">
          <h4 class="card-title">培养方案（{{ plan.items.length }} 门课）</h4>
          <div class="course-list">
            <div v-for="it in plan.items" :key="it.course" class="course-row">
              <span class="term">{{ termLabel(it) }}</span>
              <span class="course">{{ it.course }}</span>
              <span class="credits">{{ it.credits }}学分 · {{ it.campus }}</span>
            </div>
          </div>
        </section>

        <section v-if="plan.warnings.length" class="card">
          <h4 class="card-title">注意事项</h4>
          <p v-for="w in plan.warnings" :key="w" class="warn">{{ w }}</p>
        </section>

        <section v-if="plan.alternatives.length" class="card">
          <h4 class="card-title">备选方案（整体推迟一学期）</h4>
          <p class="alt">{{ plan.alternatives[0].map(it => it.course).join('、') }}</p>
        </section>
      </template>

      <router-link to="/course-planning" class="btn-primary cta">查看完整课程规划</router-link>
    </template>

    <div v-else class="loading">生成报告中…</div>
  </div>
</template>

<style scoped>
.head-card { display: flex; flex-direction: column; gap: var(--space-2); }
.report-tag { font-size: var(--text-xs); color: var(--brand-strong); }
.head-card h3 { font-size: var(--text-xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.meta { font-size: var(--text-xs); color: var(--text-muted); }
.score-row { display: flex; gap: var(--space-6); margin-top: var(--space-2); }
.score { display: flex; flex-direction: column; gap: 2px; }
.score-k { font-size: var(--text-xs); color: var(--text-muted); }
.score-v { font-size: var(--text-lg); font-weight: var(--weight-bold); color: var(--brand-strong); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }

.score-list { display: flex; flex-direction: column; gap: var(--space-2); }
.score-line { display: flex; justify-content: space-between; font-size: var(--text-sm); color: var(--text-secondary); }

.risk { font-size: var(--text-sm); color: var(--accent-purple); line-height: 1.6; }
.warn { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.chip-row { display: flex; flex-wrap: wrap; gap: var(--space-2); }

.course-list { display: flex; flex-direction: column; gap: var(--space-2); }
.course-row { display: flex; align-items: center; gap: var(--space-3); font-size: var(--text-sm); }
.term { font-size: var(--text-xs); font-weight: var(--weight-semibold); color: var(--brand-strong); min-width: 44px; }
.course { flex: 1; color: var(--text-primary); }
.credits { font-size: var(--text-xs); color: var(--text-muted); white-space: nowrap; }

.alt { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.empty { text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-muted); }
.link-btn { display: inline-block; margin-top: var(--space-3); padding: var(--space-2) var(--space-5); background: var(--brand-strong); color: #fff; border-radius: var(--radius-md); text-decoration: none; font-size: var(--text-sm); }

.cta { display: block; text-align: center; text-decoration: none; margin-top: var(--space-2); }
.loading { text-align: center; padding: var(--space-8) 0; color: var(--text-muted); }
</style>
