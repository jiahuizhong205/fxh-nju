<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchPrograms, fetchPlan, type Program, type PlanResult, type PlanItem } from '../api/client'
import BackButton from '../components/BackButton.vue'

const programs = ref<Program[]>([])
const program = ref('')
const plan = ref<PlanResult | null>(null)
const loading = ref(false)
const error = ref('')

const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八']
const phases = [
  { key: 'sprout', label: '萌芽期' },
  { key: 'leaf', label: '展叶期' },
  { key: 'flower', label: '繁花期' },
] as const
const activePhase = ref<(typeof phases)[number]['key']>('leaf')
const selectedTerm = ref('')

function phaseForYear(year: number) {
  if (year <= 2) return 'sprout'
  if (year <= 4) return 'leaf'
  return 'flower'
}

function termKey(it: PlanItem) {
  return `${it.year}-${it.term}`
}

const phaseItems = computed(() => plan.value?.items.filter(it => phaseForYear(it.year) === activePhase.value) ?? [])
const timelineItems = computed(() => {
  const seen = new Set<string>()
  return phaseItems.value.filter(it => {
    const key = termKey(it)
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
})
const visibleItems = computed(() => {
  if (!selectedTerm.value) return phaseItems.value
  return phaseItems.value.filter(it => termKey(it) === selectedTerm.value)
})

onMounted(async () => {
  loading.value = true
  try {
    programs.value = await fetchPrograms()
    const firstAvailable = programs.value.find(p => p.has_plan !== false)
    if (firstAvailable) {
      program.value = firstAvailable.name
      await loadPlan()
    } else {
      error.value = '当前没有可展示的结构化培养方案。'
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '培养方案加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
})

async function loadPlan() {
  if (!program.value) return
  loading.value = true
  error.value = ''
  plan.value = null
  try {
    plan.value = await fetchPlan(program.value)
    const first = plan.value.items[0]
    if (first) {
      activePhase.value = phaseForYear(first.year)
      selectedTerm.value = termKey(first)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '培养方案加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function termLabel(it: PlanItem): string {
  return `大${CN_NUM[it.year] ?? it.year}·${it.term}`
}

function selectPhase(key: (typeof phases)[number]['key']) {
  activePhase.value = key
  selectedTerm.value = ''
  if (phaseItems.value[0]) selectedTerm.value = termKey(phaseItems.value[0])
}

function exportPlan() {
  if (!plan.value) return
  const lines = [
    `${program.value}辅修培养日历`,
    '',
    ...plan.value.items.map(it => `${termLabel(it)}｜${it.course}｜${it.credits}学分｜${it.campus}`),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${program.value}-培养日历.txt`
  link.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="planning">
    <header class="head">
      <BackButton fallback="/" />
      <div>
        <h2>复合培养年轮</h2>
        <p>{{ program || '选择专业' }} 辅修方案图谱</p>
      </div>
    </header>

    <section class="picker">
      <label class="picker-label" for="program-picker">选择辅修专业</label>
      <select id="program-picker" v-model="program" @change="loadPlan">
        <option v-for="p in programs" :key="p.name" :value="p.name" :disabled="p.has_plan === false">
          {{ p.name }}{{ p.has_plan === false ? '（暂无培养方案）' : '' }}
        </option>
      </select>
    </section>

    <div v-if="loading" class="empty">正在加载培养方案…</div>
    <div v-else-if="error" class="card empty">{{ error }}</div>
    <template v-if="plan">
      <section class="phase-tabs" aria-label="培养阶段">
        <button v-for="phase in phases" :key="phase.key" type="button" :class="{ active: activePhase === phase.key }" @click="selectPhase(phase.key)">
          {{ phase.label }}
        </button>
      </section>

      <section class="timeline">
        <h3>🌾 培养年轮时间轴</h3>
        <div v-if="timelineItems.length" class="timeline-track">
          <button v-for="it in timelineItems" :key="termKey(it)" type="button" class="timeline-item" :class="{ active: selectedTerm === termKey(it) }" @click="selectedTerm = termKey(it)">
            <span class="timeline-node">◒</span>
            <span>{{ termLabel(it) }}</span>
          </button>
        </div>
        <p v-else class="timeline-empty">这个阶段暂未安排课程。</p>
      </section>

      <section v-if="visibleItems.length" class="course-list">
        <div v-for="it in visibleItems" :key="it.course" class="course-card">
          <div class="course-head">
            <h3>{{ it.course }}</h3>
            <span class="credit">{{ it.credits }} 学分</span>
          </div>
          <p class="course-desc">核心课程 · 辅修必修</p>
          <div class="course-meta">
            <div>上课时间：{{ termLabel(it) }}</div>
            <div>地点：{{ it.campus }}</div>
          </div>
        </div>
      </section>
      <p v-else class="timeline-empty">当前阶段暂无课程安排。</p>

      <section v-if="plan.warnings.length" class="conflict">
        <div class="conflict-title">注意事项</div>
        <p v-for="w in plan.warnings" :key="w">{{ w }}</p>
      </section>

      <section v-if="plan.alternatives.length" class="card">
        <h4 class="card-title">备选方案（整体推迟一学期）</h4>
        <p class="alt-line">{{ plan.alternatives[0].map((it) => it.course).join('、') }}</p>
      </section>

      <button type="button" class="export-btn" @click="exportPlan">导出我的复合成长培养日历 💧</button>
    </template>
  </div>
</template>

<style scoped>
.planning { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-5); }
.head { display: flex; align-items: center; gap: var(--space-3); }
.head h2 { font-size: var(--text-2xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.head p { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--text-muted); }

.card {
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--space-4);
}
.picker { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); }
.picker-label { font-size: var(--text-sm); color: var(--text-secondary); white-space: nowrap; }
.picker select {
  flex: 1; min-width: 0; padding: var(--space-2) var(--space-3); border: 1px solid var(--bg-green-soft);
  border-radius: var(--radius-full); font-size: var(--text-sm); font-family: inherit;
  background: var(--bg-page); color: var(--text-primary);
}
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.alt-line { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.phase-tabs { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); }
.phase-tabs button { padding: var(--space-3) var(--space-2); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); color: var(--text-primary); font: inherit; font-size: var(--text-base); font-weight: var(--weight-semibold); cursor: pointer; }
.phase-tabs button.active { border-color: var(--brand); background: var(--bg-green-faint); color: var(--brand-strong); }
.timeline { padding-top: var(--space-1); }
.timeline h3 { color: var(--accent-purple); font-size: var(--text-base); font-weight: var(--weight-semibold); }
.timeline-track { position: relative; display: flex; justify-content: space-around; gap: var(--space-2); margin-top: var(--space-4); }
.timeline-track::before { content: ''; position: absolute; top: 16px; left: 9%; right: 9%; height: 2px; background: var(--bg-green-soft); }
.timeline-item { position: relative; z-index: 1; display: flex; flex: 1; flex-direction: column; align-items: center; gap: var(--space-2); border: none; background: transparent; color: var(--text-muted); font: inherit; font-size: var(--text-sm); cursor: pointer; }
.timeline-node { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border: 2px solid var(--border); border-radius: var(--radius-full); background: var(--bg-page); color: var(--text-muted); font-size: var(--text-base); }
.timeline-item.active { color: var(--brand-strong); font-weight: var(--weight-semibold); }
.timeline-item.active .timeline-node { border-color: var(--brand); background: var(--bg-green-faint); color: var(--brand); }
.timeline-empty { padding: var(--space-3) 0; color: var(--text-muted); font-size: var(--text-sm); text-align: center; }

.course-list { display: flex; flex-direction: column; gap: var(--space-3); }
.course-card {
  background: var(--bg-surface); border: 1px solid var(--bg-green-soft);
  border-radius: var(--radius-lg); padding: var(--space-4);
}
.course-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }
.course-head h3 { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.credit { color: var(--brand-strong); font-size: var(--text-base); font-weight: var(--weight-semibold); white-space: nowrap; }
.course-desc { margin-top: var(--space-2); color: var(--text-secondary); font-size: var(--text-sm); }
.course-meta { margin-top: var(--space-4); display: flex; flex-direction: row; justify-content: space-between; gap: var(--space-3); font-size: var(--text-xs); color: var(--text-muted); }

.conflict {
  background: var(--bg-pink-soft); border-radius: var(--radius-lg); padding: var(--space-4);
}
.conflict-title { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--accent-purple); }
.conflict p { margin-top: var(--space-2); font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.5; }
.export-btn { width: 100%; padding: var(--space-3); border: 1px solid var(--brand); border-radius: var(--radius-full); background: var(--bg-surface); color: var(--brand-strong); font: inherit; font-size: var(--text-base); font-weight: var(--weight-semibold); cursor: pointer; }
.export-btn:hover { background: var(--bg-green-faint); }
</style>
