<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'

const store = useChatStore()
const reportContent = ref('')
const loading = ref(false)
const hasProfile = ref(false)

onMounted(async () => {
  const res = await fetch('/api/v1/profile')
  const data = await res.json()
  hasProfile.value = !!data.profile
})

async function getRecommendation() {
  loading.value = true
  reportContent.value = ''

  await new Promise((resolve) => {
    store.streamContent = ''
    store.streaming = true
    store.statusText = '正在分析画像并推荐...'

    fetch('/api/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: '请帮我推荐适合的辅修专业', intent: 'recommend' }),
    }).then(async (res) => {
      const reader = res.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6))
              if (d.content) reportContent.value += d.content
            } catch {}
          }
        }
      }
      loading.value = false
      store.streaming = false
      resolve(null)
    }).catch(() => {
      loading.value = false
      store.streaming = false
      resolve(null)
    })
  })
}
</script>

<template>
  <div class="recommend-page">
    <div class="report-card">
      <h2>辅修专业推荐</h2>

      <div v-if="!hasProfile" class="empty-state">
        <p>尚未填写学生画像，推荐无法进行。</p>
        <router-link to="/profile" class="link-btn">去填写画像</router-link>
      </div>

      <div v-else>
        <button class="btn-recommend" :disabled="loading" @click="getRecommendation">
          {{ loading ? '正在生成推荐...' : '生成辅修推荐报告' }}
        </button>

        <div v-if="reportContent" class="report">
          <div class="report-content" v-html="reportContent.replace(/\n/g, '<br>')" />
        </div>

        <div v-if="loading && !reportContent" class="loading-state">
          <div class="typing-dots"><span></span><span></span><span></span></div>
          <p>正在分析你的画像和辅修专业匹配度...</p>
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
  background: #7c3aed; color: #fff; border-radius: 8px; text-decoration: none; font-size: 0.9rem;
}

.btn-recommend {
  width: 100%; padding: 12px; background: #7c3aed; color: #fff;
  border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; font-weight: 500;
}
.btn-recommend:disabled { background: #c4b5fd; cursor: not-allowed; }

.report { margin-top: 20px; }
.report-content {
  padding: 16px; background: #f9fafb; border: 1px solid #e5e7eb;
  border-radius: 8px; font-size: 0.95rem; line-height: 1.7;
}

.loading-state { text-align: center; padding: 40px 0; color: #6b7280; }

.typing-dots { display: flex; gap: 4px; justify-content: center; margin-bottom: 8px; }
.typing-dots span {
  width: 8px; height: 8px; background: #7c3aed; border-radius: 50%;
  animation: bounce 1.4s infinite both;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>
