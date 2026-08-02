<script setup lang="ts">
import { ref, onMounted } from 'vue'

const major = ref('')
const careerGoals = ref('')
const report = ref('')
const loading = ref(false)

onMounted(async () => {
  const res = await fetch('/api/v1/profile')
  const data = await res.json()
  if (data.profile) {
    major.value = data.profile.major
    careerGoals.value = data.profile.career_goals || ''
  }
})

async function search() {
  loading.value = true; report.value = ''
  const query = `帮我找适合的实习岗位${careerGoals.value ? '，我想从事' + careerGoals.value : ''}`

  const res = await fetch('/api/v1/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: query, intent: 'career' }),
  })
  const reader = res.body?.getReader()
  if (!reader) { loading.value = false; return }
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    for (const line of buffer.split('\n')) {
      if (line.startsWith('data: ')) {
        try {
          const d = JSON.parse(line.slice(6))
          if (d.content) report.value += d.content
        } catch {}
      }
    }
    buffer = ''
  }
  loading.value = false
}
</script>

<template>
  <div class="career-page">
    <div class="career-card">
      <h2>职业方向探索</h2>
      <p class="desc">基于你的复合专业背景，发现匹配的实习和岗位</p>

      <div v-if="!major" class="empty-state">
        <p>尚未填写学生画像，部分匹配功能受限。</p>
        <router-link to="/profile" class="link-btn">去填写画像</router-link>
      </div>

      <div class="search-bar">
        <input v-model="careerGoals"
          placeholder="职业目标，如：希望从事传媒或互联网行业" />
        <button :disabled="loading" @click="search">
          {{ loading ? '搜索中...' : '搜索岗位' }}
        </button>
      </div>
      <p class="hint">
        {{ major ? `当前主修: ${major} | 匹配复合背景岗位` : '先填写画像获得更精准匹配' }}
      </p>

      <div v-if="report" class="report-box">
        <div class="report-content" v-html="report.replace(/\n/g, '<br>')" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.career-page { flex: 1; display: flex; justify-content: center; padding: 32px 20px; overflow-y: auto; }
.career-card { width: 100%; max-width: 660px; }
h2 { font-size: 1.3rem; margin-bottom: 4px; }
.desc { color: #6b7280; font-size: 0.9rem; margin-bottom: 20px; }

.empty-state { text-align: center; padding: 30px 0; color: #6b7280; }
.link-btn {
  display: inline-block; margin-top: 10px; padding: 6px 16px;
  background: #7c3aed; color: #fff; border-radius: 8px; text-decoration: none; font-size: 0.9rem;
}

.search-bar { display: flex; gap: 8px; margin-bottom: 6px; }
.search-bar input {
  flex: 1; padding: 10px 14px; border: 1px solid #d4d4d8; border-radius: 10px;
  font-size: 0.95rem; font-family: inherit;
}
.search-bar input:focus { border-color: #7c3aed; outline: none; }
.search-bar button {
  padding: 10px 20px; background: #7c3aed; color: #fff; border: none;
  border-radius: 8px; cursor: pointer; font-size: 0.9rem;
}
.search-bar button:disabled { background: #c4b5fd; cursor: not-allowed; }
.hint { font-size: 0.8rem; color: #9ca3af; }

.report-box { margin-top: 20px; }
.report-content {
  padding: 16px; background: #fff; border: 1px solid #e5e7eb;
  border-radius: 10px; font-size: 0.95rem; line-height: 1.7;
}
</style>
