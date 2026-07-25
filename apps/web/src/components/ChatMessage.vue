<script setup lang="ts">
import { ref } from 'vue'
import { marked } from 'marked'
import type { Citation } from '../api/client'

const props = defineProps<{
  role: string
  content: string
  citations: Citation[]
}>()

const showCitations = ref(false)

function rendered(content: string): string {
  return marked.parse(content, { breaks: true }) as string
}
</script>

<template>
  <div class="message" :class="role">
    <div class="avatar">{{ role === 'user' ? '我' : '禾' }}</div>
    <div class="bubble">
      <div v-if="role === 'assistant'" class="content" v-html="rendered(content)" />
      <div v-else class="content">{{ content }}</div>

      <div v-if="citations.length > 0" class="citations-section">
        <button class="cite-toggle" @click="showCitations = !showCitations">
          📎 {{ citations.length }} 条引用来源
        </button>
        <div v-if="showCitations" class="cite-list">
          <div v-for="c in citations" :key="c.citation_id" class="cite-item">
            <div class="cite-header">
              <span class="cite-source">{{ c.document_title }}</span>
              <span class="cite-badge" :class="'trust-' + c.trust_level">{{ c.trust_level }}</span>
            </div>
            <div class="cite-excerpt">{{ c.excerpt }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message { display: flex; gap: 10px; margin-bottom: 20px; }
.message.user { flex-direction: row-reverse; }
.message.assistant { align-items: flex-start; }

.avatar {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; font-weight: 600; flex-shrink: 0;
}
.message.user .avatar { background: #7c3aed; color: #fff; }
.message.assistant .avatar { background: #10b981; color: #fff; }

.bubble { max-width: 78%; }
.message.user .bubble { text-align: right; }
.content {
  padding: 10px 14px; border-radius: 12px; font-size: 0.95rem; line-height: 1.65;
  word-break: break-word;
}
.message.user .content { background: #7c3aed; color: #fff; border-bottom-right-radius: 4px; }
.message.assistant .content { background: #fff; color: #333; border: 1px solid #e5e7eb; border-bottom-left-radius: 4px; }

/* Markdown 内容样式 */
.content :deep(p) { margin: 0 0 6px; }
.content :deep(p:last-child) { margin-bottom: 0; }
.content :deep(ul), .content :deep(ol) { margin: 4px 0; padding-left: 20px; }
.content :deep(li) { margin-bottom: 2px; }
.content :deep(strong) { font-weight: 600; }

.citations-section { margin-top: 8px; }
.cite-toggle {
  font-size: 0.8rem; background: none; border: none;
  color: #6b7280; cursor: pointer; padding: 2px 0;
}
.cite-toggle:hover { color: #7c3aed; }

.cite-list { margin-top: 8px; }
.cite-item {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
  padding: 8px 12px; margin-bottom: 6px;
}
.cite-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.cite-source { font-size: 0.8rem; font-weight: 500; color: #374151; }
.cite-badge {
  font-size: 0.7rem; padding: 1px 6px; border-radius: 4px; font-weight: 600;
}
.trust-S { background: #dcfce7; color: #166534; }
.trust-A { background: #dbeafe; color: #1e40af; }
.trust-B { background: #fef3c7; color: #92400e; }
.trust-C { background: #fee2e2; color: #991b1b; }
.cite-excerpt { font-size: 0.8rem; color: #6b7280; line-height: 1.4; }
</style>
