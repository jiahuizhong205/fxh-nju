<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchPrograms, fetchPlan, type Program, type PlanResult, type PlanItem } from '../api/client'
import BackButton from '../components/BackButton.vue'

const programs = ref<Program[]>([])
const program = ref('')
const plan = ref<PlanResult | null>(null)
const loading = ref(false)
const error = ref('')

const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八']

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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '培养方案加载失败，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function termLabel(it: PlanItem): string {
  return `大${CN_NUM[it.year] ?? it.year}·${it.term}`
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

    <section class="card picker">
      <label class="picker-label">选择辅修专业</label>
      <select v-model="program" @change="loadPlan">
        <option v-for="p in programs" :key="p.name" :value="p.name" :disabled="p.has_plan === false">
          {{ p.name }}{{ p.has_plan === false ? '（暂无培养方案）' : '' }}
        </option>
      </select>
    </section>

    <div v-if="loading" class="empty">正在加载培养方案…</div>
    <div v-else-if="error" class="card empty">{{ error }}</div>
    <template v-if="plan">
      <section class="course-list">
        <div v-for="it in plan.items" :key="it.course" class="course-card">
          <div class="course-head">
            <h3>{{ it.course }}</h3>
            <span class="tag">{{ termLabel(it) }} · {{ it.credits }} 学分</span>
          </div>
          <div class="course-meta">
            <div>地点: {{ it.campus }}</div>
          </div>
        </div>
      </section>

      <section v-if="plan.warnings.length" class="conflict">
        <div class="conflict-title">注意事项</div>
        <p v-for="w in plan.warnings" :key="w">{{ w }}</p>
      </section>

      <section v-if="plan.alternatives.length" class="card">
        <h4 class="card-title">备选方案（整体推迟一学期）</h4>
        <p class="alt-line">{{ plan.alternatives[0].map((it) => it.course).join('、') }}</p>
      </section>
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
.picker { display: flex; align-items: center; gap: var(--space-3); }
.picker-label { font-size: var(--text-sm); color: var(--text-secondary); white-space: nowrap; }
.picker select {
  flex: 1; padding: var(--space-2) var(--space-3); border: 1px solid var(--border);
  border-radius: var(--radius-md); font-size: var(--text-sm); font-family: inherit;
  background: #fff; color: var(--text-primary);
}
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.alt-line { font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }

.course-list { display: flex; flex-direction: column; gap: var(--space-3); }
.course-card {
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--space-4);
}
.course-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-3); }
.course-head h3 { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.tag { padding: 2px var(--space-2); border-radius: var(--radius-sm); font-size: var(--text-2xs); background: var(--bg-green-soft); color: var(--brand-strong); white-space: nowrap; }
.course-meta { margin-top: var(--space-3); display: flex; flex-direction: column; gap: 2px; font-size: var(--text-xs); color: var(--text-muted); }

.conflict {
  background: var(--bg-pink-soft); border-radius: var(--radius-lg); padding: var(--space-4);
}
.conflict-title { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--accent-purple); }
.conflict p { margin-top: var(--space-2); font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.5; }
</style>
