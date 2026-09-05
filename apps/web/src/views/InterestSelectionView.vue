<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProfile, fetchPrograms, updateProfile } from '../api/client'

const router = useRouter()
const route = useRoute()

const stage = ref<1 | 2>(route.query.stage === '2' ? 2 : 1)
const saving = ref(false)
const error = ref('')
const loadingMajors = ref(true)

const grades = ['大一', '大二', '大三', '大四', '研究生']
const grade = ref('大二')
const majors = ref<string[]>([])
const major = ref('')

const interestOptions = ['数据分析', '写作创作', '商业策划', '人文哲思', '硬核科技', '设计艺术']
const interests = ref<string[]>(['写作创作', '数据分析'])

const strengthOptions = ['逻辑推理', '沟通表达', '创意思维', '数据处理', '动手实验', '组织协调', '外语能力', '编程基础', '其他']
const strengths = ref<string[]>(['逻辑推理', '创意思维'])

function toggle(list: string[], item: string) {
  const i = list.indexOf(item)
  if (i >= 0) list.splice(i, 1)
  else list.push(item)
}

onMounted(async () => {
  try {
    const [p, programs] = await Promise.all([fetchProfile(), fetchPrograms()])
    majors.value = programs.map(program => program.name)
    if (!p) {
      major.value = ''
      return
    }
    grade.value = p.grade || '大二'
    major.value = p.major || ''
    interests.value = p.interests ?? []
    strengths.value = p.strengths ?? []
  } catch (e) {
    error.value = e instanceof Error ? e.message : '专业目录加载失败，请稍后重试。'
  } finally {
    loadingMajors.value = false
  }
})

async function saveProfile() {
  saving.value = true
  error.value = ''
  try {
    await updateProfile({ grade: grade.value, major: major.value, interests: interests.value, strengths: strengths.value })
    stage.value = 2
    await router.replace({ path: '/interest-selection', query: { onboarding: '1', stage: '2' } })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '画像保存失败，请稍后重试。'
  } finally {
    saving.value = false
  }
}

function openOptional(path: string) {
  router.push({ path, query: { onboarding: '1' } })
}

function continueOnboarding() {
  localStorage.setItem('fxh_onboarding_complete', '1')
  router.push('/')
}
</script>

<template>
  <div v-if="stage === 1" class="page onboarding-page">
    <div class="stage-mark" aria-hidden="true">🌱</div>

    <header class="onboarding-head">
      <h2>告诉我你的土壤条件 🌱</h2>
    </header>

    <p class="page-sub">福小禾会根据你的主修、兴趣和能力，为你推荐最适合复合生长的方向。</p>

    <section class="profile-section">
      <h4 class="section-title">🎓 你现在是几年级？</h4>
      <div class="chips">
        <button v-for="g in grades" :key="g" class="chip" :class="{ selected: grade === g }" @click="grade = g">{{ g }}</button>
      </div>
    </section>

    <section class="profile-section major-section">
      <h4 class="section-title">🌾 主修专业 (单选)</h4>
      <div v-if="loadingMajors" class="choice-loading">正在加载南京大学专业目录…</div>
      <div v-else-if="!majors.length" class="choice-empty">暂未加载到专业目录，请稍后重试。</div>
      <div v-else class="major-select-wrap">
        <select v-model="major" class="major-select" aria-label="选择主修专业">
          <option disabled value="">请选择你的主修专业</option>
          <option v-for="m in majors" :key="m" :value="m">{{ m }}</option>
        </select>
      </div>
    </section>

    <section class="profile-section">
      <h4 class="section-title">✨ 兴趣方向 (可多选)</h4>
      <div class="chips">
        <button v-for="o in interestOptions" :key="o" class="chip" :class="{ selected: interests.includes(o) }" @click="toggle(interests, o)">{{ o }}</button>
      </div>
    </section>

    <section class="profile-section">
      <h4 class="section-title">💪 能力特长 (可多选)</h4>
      <div class="chips">
        <button v-for="o in strengthOptions" :key="o" class="chip" :class="{ selected: strengths.includes(o) }" @click="toggle(strengths, o)">{{ o }}</button>
      </div>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <button class="btn-primary" :disabled="saving || loadingMajors || !major" @click="saveProfile">{{ saving ? '正在整理你的画像…' : '播下种子，开始生长' }}</button>
  </div>

  <div v-else class="welcome-page">
    <div class="welcome-mark" aria-hidden="true"><span>🌱</span><span>🌿</span></div>
    <div class="welcome-illustration"><img src="/illustrations/mascot.png" alt="" /></div>
    <p class="welcome-kicker">你的花园已经准备好了</p>
    <h2>欢迎使用福小禾</h2>
    <p class="welcome-copy">从一颗种子开始，福小禾会陪你探索辅修方向、安排学习计划，让不同学科在你的花园里一起生长。</p>

    <div class="welcome-card">
      <div><span>🌾</span><strong>认识你的土壤</strong><small>{{ major }} · {{ grade }}</small></div>
      <div><span>🌱</span><strong>发现复合方向</strong><small>根据兴趣与能力生成推荐</small></div>
      <div><span>💧</span><strong>一起持续生长</strong><small>规划课程与学习节奏</small></div>
    </div>

    <section class="optional-section">
      <div class="optional-heading">
        <h3>要先完善哪些偏好？</h3>
        <span>可选</span>
      </div>
      <p>现在不填写也没关系，之后可以在设置中继续完善。</p>
      <div class="optional-list">
        <button type="button" class="optional-item" @click="openOptional('/time-preference')">
          <span class="optional-icon">⏰</span>
          <span class="optional-copy"><strong>排课时间偏好</strong><small>告诉福小禾你什么时候学习效率最高</small></span>
          <span class="optional-arrow" aria-hidden="true">›</span>
        </button>
        <button type="button" class="optional-item" @click="openOptional('/conflict-resolution')">
          <span class="optional-icon">🔀</span>
          <span class="optional-copy"><strong>辅修冲突处理</strong><small>提前选择课程冲突时的应对方式</small></span>
          <span class="optional-arrow" aria-hidden="true">›</span>
        </button>
      </div>
    </section>

    <button class="btn-primary" @click="continueOnboarding">开始探索福小禾 🌿</button>
  </div>
</template>

<style scoped>
.onboarding-page { gap: var(--space-4); }
.stage-mark { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-size: var(--text-xl); }
.onboarding-head h2 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.page-sub { line-height: 1.6; }
.profile-section { padding: var(--space-2) 0; }
.section-title { margin-bottom: var(--space-3); font-size: var(--text-xl); font-weight: var(--weight-semibold); color: var(--accent-purple); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.choice-loading, .choice-empty { color: var(--text-muted); font-size: var(--text-sm); }
.chip { padding: var(--space-2) var(--space-4); font-size: var(--text-md); }
.major-select-wrap { position: relative; }
.major-select-wrap::after { content: ''; position: absolute; top: 50%; right: var(--space-4); width: 8px; height: 8px; border-right: 1.5px solid var(--accent-purple); border-bottom: 1.5px solid var(--accent-purple); transform: translateY(-65%) rotate(45deg); pointer-events: none; }
.major-select { width: 100%; min-height: 40px; padding: var(--space-2) 48px var(--space-2) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-full); background: var(--bg-surface); color: var(--text-secondary); font: inherit; font-size: var(--text-md); line-height: 1.4; appearance: none; cursor: pointer; }
.major-select:focus { outline: 2px solid var(--accent-purple-soft); border-color: var(--accent-purple); }
.major-select option:disabled { color: var(--text-muted); }
.error { margin: 0; color: #c65b5b; font-size: var(--text-xs); }
.welcome-page { display: flex; flex-direction: column; align-items: center; min-height: 100%; padding: var(--space-5) var(--space-4) var(--space-8); text-align: center; }
.welcome-mark { align-self: flex-start; display: flex; gap: var(--space-2); font-size: var(--text-xl); }
.welcome-illustration { margin-top: var(--space-6); width: 116px; height: 116px; }
.welcome-illustration img { width: 100%; height: 100%; }
.welcome-kicker { margin-top: var(--space-5); color: var(--brand-strong); font-size: var(--text-sm); }
.welcome-page h2 { margin-top: var(--space-2); color: var(--accent-purple); font-size: var(--text-4xl); font-weight: var(--weight-bold); }
.welcome-copy { max-width: 340px; margin-top: var(--space-3); color: var(--text-secondary); font-size: var(--text-md); line-height: 1.8; }
.welcome-card { width: 100%; max-width: 390px; display: flex; flex-direction: column; gap: var(--space-3); margin-top: var(--space-6); padding: var(--space-4); border: 1px solid var(--bg-green-soft); border-radius: var(--radius-xl); background: var(--bg-green-faint); text-align: left; }
.welcome-card > div { display: grid; grid-template-columns: 32px 1fr; column-gap: var(--space-2); align-items: center; }
.welcome-card > div > span { grid-row: span 2; font-size: var(--text-xl); text-align: center; }
.welcome-card strong { color: var(--text-primary); font-size: var(--text-sm); }
.welcome-card small { margin-top: 2px; color: var(--text-muted); font-size: var(--text-xs); }
.optional-section { width: 100%; max-width: 390px; margin-top: var(--space-5); text-align: left; }
.optional-heading { display: flex; align-items: baseline; justify-content: space-between; gap: var(--space-3); }
.optional-heading h3 { color: var(--text-primary); font-size: var(--text-base); font-weight: var(--weight-semibold); }
.optional-heading span { color: var(--brand-strong); font-size: var(--text-xs); }
.optional-section > p { margin-top: var(--space-1); color: var(--text-muted); font-size: var(--text-xs); }
.optional-list { display: flex; flex-direction: column; gap: var(--space-2); margin-top: var(--space-3); }
.optional-item { display: flex; align-items: center; width: 100%; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); color: inherit; text-align: left; cursor: pointer; }
.optional-item:hover { border-color: var(--brand); }
.optional-icon { flex-shrink: 0; font-size: var(--text-xl); }
.optional-copy { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 2px; }
.optional-copy strong { color: var(--text-primary); font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.optional-copy small { color: var(--text-muted); font-size: var(--text-xs); line-height: 1.4; }
.optional-arrow { flex-shrink: 0; color: var(--brand-strong); font-size: var(--text-2xl); line-height: 1; }
.welcome-page .btn-primary { max-width: 390px; margin-top: auto; }
</style>
