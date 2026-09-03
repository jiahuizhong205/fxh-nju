<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchProfile, recommendPrograms, type Recommendation } from '../api/client'

const recommendations = ref<Recommendation[]>([])
const loading = ref(false)
const hasProfile = ref(false)

const scoreKeys = ['interest_fit', 'career_fit', 'prerequisite_readiness', 'schedule_feasibility', 'campus_feasibility']
const scoreLabel: Record<string, string> = {
  interest_fit: '兴趣匹配', career_fit: '职业匹配', prerequisite_readiness: '先修准备',
  schedule_feasibility: '排课可行', campus_feasibility: '校区可行',
}

onMounted(async () => {
  const p = await fetchProfile()
  hasProfile.value = !!p
})

async function getRecommendation() {
  loading.value = true
  try {
    recommendations.value = await recommendPrograms()
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="recommend-page">
    <div class="report-card">
      <h2>辅修专业推荐</h2>

      <div v-if="!hasProfile" class="empty-state">
        <p>尚未填写学生画像，推荐无法进行。</p>
        <router-link to="/edit-profile" class="link-btn">去填写画像</router-link>
      </div>

      <div v-else>
        <button class="btn-recommend" :disabled="loading" @click="getRecommendation">
          {{ loading ? '正在生成推荐...' : '生成辅修推荐' }}
        </button>

        <div v-if="recommendations.length" class="rec-list">
          <div v-for="(r, i) in recommendations" :key="r.program.name" class="rec-card">
            <div class="rec-head">
              <h3>[{{ i + 1 }}] {{ r.program.name }}</h3>
              <span class="rec-score">{{ (r.total_score * 100).toFixed(0) }}%</span>
            </div>
            <p class="rec-meta">{{ r.program.discipline }} · 学科评估 {{ r.program.subject_rank }} · {{ r.program.campus }}</p>

            <div class="rec-scores">
              <div v-for="k in scoreKeys" :key="k" class="score-row">
                <span>{{ scoreLabel[k] }}</span>
                <span>{{ ((r.scores[k] ?? 0) * 100).toFixed(0) }}%</span>
              </div>
            </div>

            <p class="rec-courses">核心课程：{{ r.program.core_courses.slice(0, 4).join('、') }}</p>
            <p v-if="r.risks.length" class="rec-risks">⚠ {{ r.risks.join('；') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommend-page {
  flex: 1; display: flex; justify-content: center; padding: 32px 20px; overflow-y: auto;
}
.report-card {
  width: 100%; max-width: 640px; background: #fff;
  border-radius: 12px; padding: 28px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
h2 { font-size: 1.3rem; margin-bottom: 16px; }

.empty-state { text-align: center; padding: 40px 0; color: #6b7280; }
.link-btn {
  display: inline-block; margin-top: 12px; padding: 8px 20px;
  background: #5a7a6b; color: #fff; border-radius: 8px; text-decoration: none; font-size: 0.9rem;
}

.btn-recommend {
  width: 100%; padding: 12px; background: #5a7a6b; color: #fff;
  border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 500;
}
.btn-recommend:disabled { background: #dce6d2; cursor: not-allowed; }

.rec-list { margin-top: 20px; display: flex; flex-direction: column; gap: 16px; }
.rec-card {
  padding: 16px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
}
.rec-head { display: flex; justify-content: space-between; align-items: center; }
.rec-head h3 { font-size: 1.05rem; }
.rec-score { font-size: 1.1rem; font-weight: 600; color: #5a7a6b; }
.rec-meta { margin-top: 4px; font-size: 0.85rem; color: #6b7280; }

.rec-scores { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.score-row { display: flex; justify-content: space-between; font-size: 0.9rem; color: #374151; }

.rec-courses { margin-top: 12px; font-size: 0.85rem; color: #6b7280; }
.rec-risks { margin-top: 8px; font-size: 0.85rem; color: #b45309; }
</style>
