<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchProfile, recommendPrograms, fetchPlan, type Recommendation, type PlanResult, type PlanItem } from '../api/client'
import BackButton from '../components/BackButton.vue'

const rec = ref<Recommendation | null>(null)
const plan = ref<PlanResult | null>(null)
const hasProfile = ref(false)
const error = ref('')

const scoreKeys = ['interest_fit', 'career_fit', 'prerequisite_readiness', 'schedule_feasibility', 'campus_feasibility']
const scoreLabel: Record<string, string> = {
  interest_fit: '兴趣匹配', career_fit: '职业匹配', prerequisite_readiness: '先修准备',
  schedule_feasibility: '排课可行', campus_feasibility: '校区可行',
}
const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八']

onMounted(async () => {
  try {
    const p = await fetchProfile()
    hasProfile.value = !!p
    if (!p) return
    const recs = await recommendPrograms()
    if (!recs.length) {
      error.value = '暂时没有可生成报告的推荐结果。'
      return
    }
    rec.value = recs[0]
    try {
      plan.value = await fetchPlan(recs[0].program.name)
    } catch (e) {
      error.value = e instanceof Error ? e.message : '该专业暂未录入结构化培养方案。'
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '报告加载失败，请稍后重试。'
  }
})

function termLabel(it: PlanItem): string {
  return `大${CN_NUM[it.year] ?? it.year}·${it.term}`
}
</script>

<template>
  <div class="page report-page">
    <header class="page-head">
      <BackButton fallback="/recommend" />
      <div>
        <h2>辅修推荐分析报告 🌱</h2>
        <p>福小禾帮你看清这颗种子的成长路线</p>
      </div>
    </header>

    <div v-if="!hasProfile" class="card empty">
      <p>尚未填写学生画像，无法生成报告。</p>
      <router-link to="/edit-profile" class="link-btn">去填写画像</router-link>
    </div>

    <template v-else-if="rec">
      <section class="card head-card">
        <div class="report-meta"><span>🏛️ 南京大学 · {{ rec.program.discipline }}</span><span class="degree-tag">辅修方案</span></div>
        <p class="report-tag">推荐方向 · {{ rec.program.discipline }}</p>
        <h3>{{ rec.program.name }}</h3>
        <p class="meta">{{ rec.program.discipline }} · 学科评估 {{ rec.program.subject_rank }} · {{ rec.program.campus }}</p>
        <div class="score-row overview-row">
          <div class="score">
            <span class="score-k">综合匹配</span>
            <span class="score-v">{{ (rec.total_score * 100).toFixed(0) }}%</span>
          </div>
          <div class="score">
            <span class="score-k">需修学分</span>
            <span class="score-v">{{ rec.program.total_credits }}</span>
          </div>
          <div class="score">
            <span class="score-k">培养学期</span>
            <span class="score-v">{{ rec.program.semesters_needed }}</span>
          </div>
        </div>
        <div class="head-tags"><span v-for="m in rec.program.core_courses.slice(0, 3)" :key="m" class="chip">{{ m }}</span></div>
      </section>

      <section class="card">
        <h4 class="card-title">📊 与你的画像匹配度</h4>
        <div class="score-list">
          <div v-for="k in scoreKeys" :key="k" class="score-line">
            <div class="score-label"><span>{{ scoreLabel[k] }}</span><strong>{{ ((rec.scores[k] ?? 0) * 100).toFixed(0) }}%</strong></div>
            <div class="score-track"><span :style="{ width: `${((rec.scores[k] ?? 0) * 100).toFixed(0)}%` }" /></div>
          </div>
        </div>
      </section>

      <section v-if="rec.risks.length" class="card">
        <h4 class="card-title">⚠️ 需要提前留意</h4>
        <p v-for="r in rec.risks" :key="r" class="risk">⚠ {{ r }}</p>
      </section>

      <section class="card">
        <h4 class="card-title">📚 课程体系解析</h4>
        <p class="section-note">共 {{ rec.program.total_credits }} 学分 · {{ rec.program.semesters_needed }} 个培养学期</p>
        <div class="chip-row">
          <span v-for="c in rec.program.core_courses" :key="c" class="chip">{{ c }}</span>
        </div>
      </section>

      <section class="card qualification-card">
        <h4 class="card-title">🎓 学分与学位资格</h4>
        <div class="qualification-row"><span>培养方案总学分</span><strong>{{ rec.program.total_credits }} 学分</strong></div>
        <div class="qualification-row"><span>数学先修要求</span><strong>{{ rec.program.required_math ? rec.program.required_math_level || '需要' : '暂无要求' }}</strong></div>
        <div class="qualification-row"><span>培养校区</span><strong>{{ rec.program.campus || '暂未标注' }}</strong></div>
      </section>

      <section v-if="error" class="card empty">
        <p>{{ error }}</p>
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

      <router-link to="/course-planning" class="btn-primary cta">🌱 种下这颗种子，开启培养计划</router-link>
    </template>

    <div v-else-if="error" class="card empty"><p>{{ error }}</p></div>
    <div v-else class="loading">生成报告中…</div>
  </div>
</template>

<style scoped>
.report-page { gap: var(--space-4); padding-top: var(--space-5); }
.page-head h2 { font-size: var(--text-xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.page-head p { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--brand-strong); }
.head-card { display: flex; flex-direction: column; gap: var(--space-2); border-color: var(--bg-green-soft); }
.report-meta { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); color: var(--text-secondary); font-size: var(--text-sm); }
.degree-tag { padding: 3px var(--space-2); border-radius: var(--radius-full); background: var(--accent-purple-soft); color: var(--accent-purple); font-size: var(--text-2xs); }
.report-tag { font-size: var(--text-xs); color: var(--brand-strong); }
.head-card h3 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.meta { font-size: var(--text-xs); color: var(--text-muted); }
.score-row { display: flex; gap: var(--space-6); margin-top: var(--space-2); }
.overview-row { padding: var(--space-3) 0; border-top: 1px solid var(--bg-subtle); border-bottom: 1px solid var(--bg-subtle); }
.score { display: flex; flex-direction: column; gap: 2px; }
.score-k { font-size: var(--text-xs); color: var(--text-muted); }
.score-v { font-size: var(--text-lg); font-weight: var(--weight-bold); color: var(--brand-strong); }
.head-tags { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.head-tags .chip { color: var(--text-secondary); background: var(--bg-green-faint); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }

.score-list { display: flex; flex-direction: column; gap: var(--space-3); }
.score-line { display: flex; flex-direction: column; gap: var(--space-1); font-size: var(--text-sm); color: var(--text-secondary); }
.score-label { display: flex; justify-content: space-between; gap: var(--space-2); }
.score-label strong { color: var(--accent-purple); font-size: var(--text-xs); }
.score-track { height: 6px; border-radius: var(--radius-full); background: var(--bg-subtle); overflow: hidden; }
.score-track span { display: block; height: 100%; border-radius: inherit; background: var(--brand-gradient); }

.risk { font-size: var(--text-sm); color: var(--accent-purple); line-height: 1.6; }
.warn { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }
.section-note { margin-top: calc(var(--space-2) * -1); margin-bottom: var(--space-3); color: var(--text-muted); font-size: var(--text-xs); }

.chip-row { display: flex; flex-wrap: wrap; gap: var(--space-2); }

.course-list { display: flex; flex-direction: column; gap: var(--space-2); }
.course-row { display: flex; align-items: center; gap: var(--space-3); font-size: var(--text-sm); }
.term { font-size: var(--text-xs); font-weight: var(--weight-semibold); color: var(--brand-strong); min-width: 44px; }
.course { flex: 1; color: var(--text-primary); }
.credits { font-size: var(--text-xs); color: var(--text-muted); white-space: nowrap; }

.alt { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.qualification-card { border-color: var(--bg-green-soft); }
.qualification-row { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--bg-subtle); font-size: var(--text-sm); }
.qualification-row:last-child { border-bottom: none; }
.qualification-row span { color: var(--text-muted); }
.qualification-row strong { color: var(--text-primary); text-align: right; }

.empty { text-align: center; padding: var(--space-8) var(--space-4); color: var(--text-muted); }
.link-btn { display: inline-block; margin-top: var(--space-3); padding: var(--space-2) var(--space-5); background: var(--brand-strong); color: #fff; border-radius: var(--radius-md); text-decoration: none; font-size: var(--text-sm); }

.cta { display: block; position: sticky; bottom: var(--space-2); text-align: center; text-decoration: none; margin-top: var(--space-2); box-shadow: 0 6px 16px rgba(47, 59, 53, .12); }
.loading { text-align: center; padding: var(--space-8) 0; color: var(--text-muted); }
</style>
