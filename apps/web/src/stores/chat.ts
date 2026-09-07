import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  sendMessage,
  fetchConversations,
  fetchMessages,
  type Citation,
  type Conversation,
  type ChatMessage,
} from '../api/client'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const messages = ref<ChatMessage[]>([])
  const currentConvId = ref<string | null>(null)
  const streaming = ref(false)
  const streamContent = ref('')
  const streamCitations = ref<Citation[]>([])
  const statusText = ref('')
  const error = ref('')
  const lastFailedMessage = ref('')

  let controller: AbortController | null = null

  // crypto.randomUUID 仅在安全上下文中保证可用；公网 HTTP 临时部署时也要能发送消息。
  function createMessageId(): string {
    if (typeof globalThis.crypto?.randomUUID === 'function') {
      return globalThis.crypto.randomUUID()
    }
    return `local-${Date.now()}-${Math.random().toString(16).slice(2)}`
  }

  async function loadConversations() {
    conversations.value = await fetchConversations()
  }

  async function loadMessages(convId: string) {
    currentConvId.value = convId
    messages.value = await fetchMessages(convId)
  }

  async function send(msg: string) {
    if (!msg.trim() || streaming.value) return

    error.value = ''
    lastFailedMessage.value = ''
    streamContent.value = ''
    streamCitations.value = []
    streaming.value = true
    statusText.value = '正在检索政策文档...'

    messages.value.push({
      id: createMessageId(),
      role: 'user',
      content: msg,
      citations: [],
      created_at: new Date().toISOString(),
    })

    controller = sendMessage(
      msg,
      currentConvId.value,
      (node, statusMsg) => { statusText.value = statusMsg },
      (text) => { streamContent.value += text },
      (cit) => { streamCitations.value.push(cit) },
      (final) => {
        messages.value.push({
          id: createMessageId(),
          role: 'assistant',
          content: final.content,
          citations: final.citations,
          created_at: new Date().toISOString(),
        })
        if (final.conversation_id && !currentConvId.value) {
          currentConvId.value = final.conversation_id
          loadConversations()
        }
        streamContent.value = ''
        streamCitations.value = []
        streaming.value = false
        statusText.value = ''
      },
      (err) => {
        error.value = err
        lastFailedMessage.value = msg
        streaming.value = false
        statusText.value = ''
      },
    )
  }

  function cancel() {
    controller?.abort()
    streaming.value = false
    statusText.value = ''
  }

  function newChat() {
    // ChatView 挂载、路由切换与发送极接近时，不能清掉已显示的提问。
    if (streaming.value) return
    currentConvId.value = null
    messages.value = []
    streamContent.value = ''
    streamCitations.value = []
    error.value = ''
    lastFailedMessage.value = ''
  }

  function retry() {
    if (lastFailedMessage.value) send(lastFailedMessage.value)
  }

  return {
    conversations, messages, currentConvId, streaming,
    streamContent, streamCitations, statusText, error, lastFailedMessage,
    loadConversations, loadMessages, send, cancel, newChat, retry,
  }
})
