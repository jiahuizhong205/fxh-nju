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
              <a v-if="c.source_url" class="cite-source cite-link" :href="c.source_url" target="_blank" rel="noopener noreferrer">{{ c.document_title }} ↗</a>
              <span v-else class="cite-source">{{ c.document_title }}</span>
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
.message { display: flex; gap: 10px; margin-bottom: var(--space-5); }
.message.user { flex-direction: row-reverse; }
.message.assistant { align-items: flex-start; }

.avatar {
  width: 34px; height: 34px; border-radius: var(--radius-full);
  display: flex; align-items: center; justify-content: center;
  font-size: var(--text-sm); font-weight: var(--weight-semibold); flex-shrink: 0;
}
.message.user .avatar { background: var(--brand-strong); color: #fff; }
.message.assistant .avatar { background: var(--brand); color: #fff; }

.bubble { max-width: 78%; }
.message.user .bubble { text-align: right; }
.content {
  padding: 10px 14px; border-radius: var(--radius-md); font-size: var(--text-base); line-height: 1.65;
  word-break: break-word;
}
.message.user .content { background: var(--brand-strong); color: #fff; border-bottom-right-radius: 4px; }
.message.assistant .content { background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border); border-bottom-left-radius: 4px; }

/* Markdown 内容样式 */
.content :deep(p) { margin: 0 0 6px; }
.content :deep(p:last-child) { margin-bottom: 0; }
.content :deep(ul), .content :deep(ol) { margin: 4px 0; padding-left: 20px; }
.content :deep(li) { margin-bottom: 2px; }
.content :deep(strong) { font-weight: var(--weight-semibold); }

.citations-section { margin-top: var(--space-2); }
.cite-toggle {
  font-size: var(--text-sm); background: none; border: none;
  color: var(--text-muted); cursor: pointer; padding: 2px 0;
}
.cite-toggle:hover { color: var(--brand-strong); }

.cite-list { margin-top: var(--space-2); }
.cite-item {
  background: var(--bg-subtle); border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: var(--space-2) var(--space-3); margin-bottom: var(--space-2);
}
.cite-header { display: flex; align-items: center; gap: var(--space-2); margin-bottom: 4px; }
.cite-source { font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--text-primary); }
.cite-link { color: var(--brand-strong); text-decoration: none; border-bottom: 1px dashed var(--brand-strong); }
.cite-link:hover { opacity: 0.75; }
.cite-badge {
  font-size: var(--text-2xs); padding: 1px 6px; border-radius: 4px; font-weight: var(--weight-semibold);
}
.trust-S { background: #dcfce7; color: #166534; }
.trust-A { background: #dbeafe; color: #1e40af; }
.trust-B { background: #fef3c7; color: #92400e; }
.trust-C { background: #fee2e2; color: #991b1b; }
.cite-excerpt { font-size: var(--text-sm); color: var(--text-muted); line-height: 1.4; }
</style>
