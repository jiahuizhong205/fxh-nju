<script setup lang="ts">
import { ref } from 'vue'
import { sendMessage } from '../api/client'

const mode = ref<'enrolled' | 'self_study'>('enrolled')
const question = ref('')
const answer = ref('')
const loading = ref(false)
const error = ref('')
let controller: AbortController | null = null

async function ask() {
  if (!question.value.trim()) return
  loading.value = true
  answer.value = ''
  error.value = ''
  controller = sendMessage(
    question.value,
    null,
    () => {},
    text => { answer.value += text },
    () => {},
    final => {
      if (!answer.value) answer.value = final.content
      loading.value = false
    },
    err => {
      error.value = err
      loading.value = false
    },
    mode.value === 'enrolled' ? 'tutor_enrolled' : 'tutor_self_study',
  )
}

const enrolledTopics = [
  '帮我讲解新闻价值判断这个知识点',
  '传播学概论的核心理论是什么',
  '请结合文学分析思维解释新闻编辑',
]

const selfStudyTopics = [
  '帮我规划新闻学自学路线',
  '数据新闻需要学会哪些工具',
  '适合零基础自学者的学习步骤',
]
</script>

<template>
  <div class="tutor-page">
    <div class="tutor-card">
      <h2>漫步知识森林 🌲</h2>
      <p class="level">LV.4 园艺学者</p>
      <div class="mode-switch">
        <button :class="{ active: mode === 'enrolled' }" @click="mode = 'enrolled'">
          在校辅修小径
        </button>
        <button :class="{ active: mode === 'self_study' }" @click="mode = 'self_study'">
          独立自学小径
        </button>
      </div>
      <p class="mode-desc">
        {{ mode === 'enrolled'
           ? '结合主修教材做跨学科讲解，让辅修知识更易理解'
           : '为你整合自学资源，生成知识树和学习路线' }}
      </p>

      <div class="topic-suggestions">
        <span class="label">试试这些：</span>
        <button
          v-for="t in (mode === 'enrolled' ? enrolledTopics : selfStudyTopics)"
          :key="t" class="topic-btn"
          @click="question = t; ask()"
        >{{ t }}</button>
      </div>

      <div class="qa-area">
        <textarea v-model="question"
          :placeholder="mode === 'enrolled' ? '输入你想理解的知识点...' : '输入你想学习的技能或方向...'"
          rows="3" />
        <button :disabled="loading || !question.trim()" @click="ask">
          {{ loading ? '生成中...' : '提问' }}
        </button>
      </div>

      <div v-if="answer" class="answer-box">
        <div class="answer-content" v-html="answer.replace(/\n/g, '<br>')" />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.tutor-page { flex: 1; display: flex; justify-content: center; padding: 32px 20px; overflow-y: auto; }
.tutor-card { width: 100%; max-width: 660px; }
h2 { font-size: 1.3rem; margin-bottom: 4px; }
.level { color: var(--brand-strong); font-size: 0.8rem; margin-bottom: 12px; }

.mode-switch { display: flex; gap: 4px; margin-bottom: 8px; }
.mode-switch button {
  flex: 1; padding: 10px; border: 1px solid #d4d4d8; background: #fff;
  border-radius: 8px; cursor: pointer; font-size: 0.9rem;
}
.mode-switch button.active { background: #5a7a6b; color: #fff; border-color: #5a7a6b; }
.mode-desc { color: #6b7280; font-size: 0.85rem; margin-bottom: 16px; }

.topic-suggestions { margin-bottom: 16px; }
.topic-suggestions .label { font-size: 0.8rem; color: #9ca3af; margin-right: 8px; }
.topic-btn {
  padding: 4px 12px; background: #f3f4f6; border: 1px solid #e5e7eb;
  border-radius: 16px; cursor: pointer; font-size: 0.8rem; margin: 2px 4px;
  color: #5a7a6b;
}
.topic-btn:hover { background: #f4f8f2; }

.qa-area { display: flex; gap: 8px; align-items: flex-end; }
.qa-area textarea {
  flex: 1; padding: 10px 14px; border: 1px solid #d4d4d8; border-radius: 10px;
  font-size: 0.95rem; font-family: inherit; resize: none;
}
.qa-area textarea:focus { border-color: #5a7a6b; outline: none; }
.qa-area button {
  padding: 10px 20px; background: #5a7a6b; color: #fff; border: none;
  border-radius: 8px; cursor: pointer; font-size: 0.9rem;
}
.qa-area button:disabled { background: #dce6d2; cursor: not-allowed; }

.answer-box { margin-top: 20px; }
.answer-content {
  padding: 16px; background: #fff; border: 1px solid #e5e7eb;
  border-radius: 10px; font-size: 0.95rem; line-height: 1.7;
}
.error { margin-top: 12px; color: #b45309; font-size: 0.9rem; }
</style>
