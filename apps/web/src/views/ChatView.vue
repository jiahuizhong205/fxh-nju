<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import ChatMessage from '../components/ChatMessage.vue'

const store = useChatStore()
const input = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const showSidebar = ref(false)

onMounted(() => {
  store.newChat()
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

function handleNewChat() {
  store.newChat()
  input.value = ''
}
</script>

<template>
  <div class="chat-layout">
    <!-- 会话列表抽屉 -->
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
      <header class="chat-head">
        <router-link to="/" class="back">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="m15 18-6-6 6-6"/>
          </svg>
        </router-link>
        <h2>政策答疑</h2>
        <button class="btn-newchat" @click="handleNewChat">＋ 新对话</button>
        <button class="history-btn" @click="showSidebar = !showSidebar">☰</button>
      </header>

      <div ref="messagesEl" class="messages">
        <div v-if="store.messages.length === 0 && !store.streaming" class="welcome">
          <h2>福小禾伴学精灵智能问答 🌱</h2>
          <p>你好呀！我是你的伴学精灵福小禾，可以问我辅修政策、学分要求、证书规则等问题。</p>
          <div class="quick-questions">
            <button
              v-for="q in ['辅修毕业设计要求', '学分互认政策', '双学位收费标准']"
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
          placeholder="向福小禾提问关于辅修的一切..."
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
.chat-layout { height: 100%; display: flex; overflow: hidden; position: relative; }

.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; z-index: 20;
  width: 260px; background: var(--bg-surface); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; transform: translateX(-100%);
  transition: transform 0.2s;
}
.sidebar.open { transform: translateX(0); }
.sidebar-header { padding: var(--space-3); }
.btn-new {
  width: 100%; padding: var(--space-2); background: var(--brand-strong); color: #fff;
  border: none; border-radius: var(--radius-md); cursor: pointer; font-size: var(--text-base);
}
.conv-list { flex: 1; overflow-y: auto; }
.conv-item {
  padding: var(--space-3) var(--space-4); cursor: pointer; border-bottom: 1px solid var(--bg-subtle);
  font-size: var(--text-base); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  color: var(--text-secondary);
}
.conv-item:hover { background: var(--bg-green-faint); }
.conv-item.active { background: var(--bg-green-faint); color: var(--brand-strong); font-weight: var(--weight-medium); }

.overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.3); z-index: 15; }

.chat-main {
  flex: 1; display: flex; flex-direction: column; overflow: hidden;
}

.chat-head {
  display: flex; align-items: center; gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--bg-page); border-bottom: 1px solid var(--border); flex-shrink: 0;
}
.chat-head h2 { flex: 1; text-align: center; font-size: var(--text-lg); font-weight: var(--weight-bold); color: var(--text-primary); }
.btn-newchat {
  padding: var(--space-1) var(--space-3); border-radius: var(--radius-full);
  background: var(--brand-strong); color: #fff; border: none; cursor: pointer;
  font-size: var(--text-sm); font-weight: var(--weight-medium); white-space: nowrap;
}
.history-btn {
  width: 36px; height: 36px; border-radius: var(--radius-full);
  background: var(--bg-surface); border: 1px solid var(--border);
  color: var(--text-secondary); cursor: pointer; font-size: var(--text-base);
  display: flex; align-items: center; justify-content: center;
}

.messages {
  flex: 1; overflow-y: auto; padding: var(--space-4);
  display: flex; flex-direction: column;
}

.welcome {
  margin: auto; text-align: center; padding: var(--space-8) var(--space-4);
}
.welcome h2 { font-size: var(--text-xl); margin-bottom: var(--space-2); color: var(--text-primary); }
.welcome p { color: var(--text-secondary); margin-bottom: var(--space-6); }
.quick-questions { display: flex; flex-wrap: wrap; gap: var(--space-2); justify-content: center; }
.quick-btn {
  padding: var(--space-2) var(--space-4); background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-full); cursor: pointer; font-size: var(--text-sm); color: var(--brand-strong);
  transition: border-color 0.15s;
}
.quick-btn:hover { border-color: var(--brand-strong); }

.streaming-bubble { padding: var(--space-3) 0; }
.streaming-status { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.streaming-content { font-size: var(--text-base); line-height: 1.6; color: var(--text-primary); }

.typing-dots { display: flex; gap: 4px; }
.typing-dots span {
  width: 6px; height: 6px; background: var(--brand); border-radius: var(--radius-full);
  animation: bounce 1.4s infinite both;
}
.typing-dots span:nth-child(2) { animation-delay: 0.2s; }
.typing-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  padding: var(--space-3) var(--space-4); background: var(--bg-surface); border-top: 1px solid var(--border);
  display: flex; gap: var(--space-2); align-items: flex-end;
}
.input-area textarea {
  flex: 1; padding: var(--space-2) var(--space-3); border: 1px solid var(--border);
  border-radius: var(--radius-md); resize: none; font-size: var(--text-base); outline: none;
  font-family: inherit; line-height: 1.5; background: var(--bg-surface); color: var(--text-primary);
}
.input-area textarea:focus { border-color: var(--brand); }

.btn-send, .btn-cancel {
  padding: var(--space-2) var(--space-5); border: none; border-radius: var(--radius-md);
  cursor: pointer; font-size: var(--text-base); font-weight: var(--weight-medium);
}
.btn-send { background: var(--brand-strong); color: #fff; }
.btn-send:disabled { background: var(--bg-subtle); color: var(--text-muted); cursor: not-allowed; }
.btn-cancel { background: #ef4444; color: #fff; }
</style>
