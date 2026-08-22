<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import ChatMessage from '../components/ChatMessage.vue'

const store = useChatStore()
const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const showSidebar = ref(false)

onMounted(() => {
  store.loadConversations()
})

watch(
  () => store.messages.length,
  async () => { await nextTick(); scrollBottom() },
)
watch(() => store.streamContent, async () => { await nextTick(); scrollBottom() })

function scrollBottom() {
  if (messagesEl.value) {
    messagesEl.value.scrollTop = messagesEl.value.scrollHeight
  }
}

function handleSend() {
  store.send(input.value)
  input.value = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

function selectConv(id: string) {
  store.loadMessages(id)
  showSidebar.value = false
}
</script>

<template>
  <div class="chat-layout">
    <!-- 侧边栏切换 -->
    <button class="sidebar-toggle" @click="showSidebar = !showSidebar">☰</button>

    <!-- 会话列表侧边栏 -->
    <aside class="sidebar" :class="{ open: showSidebar }">
      <div class="sidebar-header">
        <button class="btn-new" @click="store.newChat(); showSidebar = false">+ 新对话</button>
      </div>
      <div class="conv-list">
        <div
          v-for="c in store.conversations" :key="c.id"
          class="conv-item"
          :class="{ active: c.id === store.currentConvId }"
          @click="selectConv(c.id)"
        >
          {{ c.title || '新对话' }}
        </div>
      </div>
    </aside>

    <!-- 遮罩 -->
    <div v-if="showSidebar" class="overlay" @click="showSidebar = false" />

    <!-- 对话区 -->
    <div class="chat-main">
      <div ref="messagesEl" class="messages">
        <div v-if="store.messages.length === 0 && !store.streaming" class="welcome">
          <h2>你好，我是福小禾 👋</h2>
          <p>南大辅修政策答疑助手，可以问我辅修政策、学分要求、证书规则等问题。</p>
          <div class="quick-questions">
            <button
              v-for="q in ['辅修和双学位有什么区别？', '辅修需要修多少学分？', '如何通过辅修转专业？']"
              :key="q"
              class="quick-btn"
              @click="store.send(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <ChatMessage
          v-for="m in store.messages" :key="m.id"
          :role="m.role"
          :content="m.content"
          :citations="m.citations"
        />

        <!-- 流式输出中 -->
        <div v-if="store.streaming" class="streaming-bubble">
          <div class="streaming-status">{{ store.statusText }}</div>
          <div v-if="store.streamContent" class="streaming-content">{{ store.streamContent }}</div>
          <div v-else class="typing-dots"><span></span><span></span><span></span></div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <textarea
          v-model="input"
          placeholder="输入你的问题，如：辅修和双学位有什么区别？"
          rows="2"
          :disabled="store.streaming"
          @keydown="handleKeydown"
        />
        <div class="input-actions">
          <button
            v-if="store.streaming"
            class="btn-cancel"
            @click="store.cancel"
          >停止</button>
          <button
            v-else
            class="btn-send"
            :disabled="!input.trim()"
            @click="handleSend"
          >发送</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-layout { display: flex; flex: 1; overflow: hidden; position: relative; }

.sidebar-toggle {
  position: absolute; top: 8px; left: 8px; z-index: 10;
  background: #fff; border: 1px solid #ddd; border-radius: 6px;
  padding: 6px 10px; cursor: pointer; font-size: 1.1rem;
}

.sidebar {
  width: 260px; background: #fff; border-right: 1px solid #e5e7eb;
  display: flex; flex-direction: column; flex-shrink: 0;
  transition: transform 0.2s;
}
@media (max-width: 640px) {
  .sidebar { position: fixed; left: 0; top: 0; bottom: 0; z-index: 20; transform: translateX(-100%); }
  .sidebar.open { transform: translateX(0); }
}

.sidebar-header { padding: 12px; }
.btn-new {
  width: 100%; padding: 8px; background: #7c3aed; color: #fff;
  border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem;
}
.conv-list { flex: 1; overflow-y: auto; }
.conv-item {
  padding: 10px 14px; cursor: pointer; border-bottom: 1px solid #f3f4f6;
  font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.conv-item:hover { background: #f9fafb; }
.conv-item.active { background: #ede9fe; color: #5b21b6; font-weight: 500; }

.overlay { display: none; }
@media (max-width: 640px) {
  .overlay { display: block; position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 15; }
}

.chat-main {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}

.messages {
  flex: 1; overflow-y: auto; padding: 16px 20px;
}

.welcome {
  text-align: center; padding: 60px 20px;
}
.welcome h2 { font-size: 1.6rem; margin-bottom: 8px; color: #333; }
.welcome p { color: #666; margin-bottom: 24px; }
.quick-questions { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.quick-btn {
  padding: 8px 16px; background: #fff; border: 1px solid #d4d4d8;
  border-radius: 20px; cursor: pointer; font-size: 0.85rem; color: #5b21b6;
  transition: border-color 0.15s;
}
.quick-btn:hover { border-color: #7c3aed; }

.streaming-bubble { padding: 12px 0; }
.streaming-status { font-size: 0.8rem; color: #9ca3af; margin-bottom: 6px; }
.streaming-content { font-size: 0.95rem; line-height: 1.6; color: #333; }

.typing-dots { display: flex; gap: 4px; }
.typing-dots span {
  width: 6px; height: 6px; background: #a78bfa; border-radius: 50%;
  animation: bounce 1.4s infinite both;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  padding: 12px 20px; background: #fff; border-top: 1px solid #e5e7eb;
  display: flex; gap: 10px; align-items: flex-end;
}
.input-area textarea {
  flex: 1; padding: 10px 14px; border: 1px solid #d4d4d8;
  border-radius: 10px; resize: none; font-size: 0.95rem; outline: none;
  font-family: inherit; line-height: 1.5;
}
.input-area textarea:focus { border-color: #7c3aed; }

.btn-send, .btn-cancel {
  padding: 8px 20px; border: none; border-radius: 8px;
  cursor: pointer; font-size: 0.9rem; font-weight: 500;
}
.btn-send { background: #7c3aed; color: #fff; }
.btn-send:disabled { background: #c4b5fd; cursor: not-allowed; }
.btn-cancel { background: #ef4444; color: #fff; }
</style>
