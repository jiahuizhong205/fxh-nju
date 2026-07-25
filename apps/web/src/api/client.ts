const BASE = '/api/v1'

export interface Citation {
  citation_id: string
  document_title: string
  chunk_index: number
  excerpt: string
  trust_level: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE}/conversations`)
  return res.json()
}

export async function fetchMessages(convId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${BASE}/conversations/${convId}/messages`)
  return res.json()
}

export function sendMessage(
  message: string,
  threadId: string | null,
  onNode: (node: string, msg: string) => void,
  onToken: (text: string) => void,
  onCitation: (cit: Citation) => void,
  onFinal: (data: any) => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()

  fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal: controller.signal,
  }).then(async (res) => {
    const convId = res.headers.get('X-Conversation-Id')
    const reader = res.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buffer = ''

    let currentEvent = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6))
            const ev = currentEvent
            currentEvent = ''

            if (ev === 'node_update') {
              onNode(data.node, data.message)
            } else if (ev === 'token') {
              onToken(data.content)
            } else if (ev === 'citation') {
              onCitation(data as Citation)
            } else if (ev === 'final') {
              onFinal({ ...data, conversation_id: convId })
            } else if (ev === 'error') {
              onError(data.message)
            }
          } catch { /* partial chunk */ }
        }
      }
    }
  }).catch(err => {
    if (err.name !== 'AbortError') {
      onError(err.message)
    }
  })

  return controller
}
