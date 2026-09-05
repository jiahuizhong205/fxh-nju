<script setup lang="ts">
import { ref } from 'vue'
import { submitFeedback } from '../api/client'
import BackButton from '../components/BackButton.vue'

const type = ref('功能建议')
const content = ref('')
const contact = ref('')
const submitted = ref(false)
const saving = ref(false)
const error = ref('')
const attachments = ref<string[]>([])

const types = ['功能建议', 'Bug反馈', '体验问题', '其他']

function onFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement
  attachments.value = Array.from(input.files ?? []).slice(0, 3).map(file => file.name)
}

async function submit() {
  if (!content.value.trim()) return
  saving.value = true
  error.value = ''
  try {
    await submitFeedback({
      feedback_type: type.value,
      content: content.value,
      contact: contact.value,
      attachments: attachments.value,
    })
    submitted.value = true
    content.value = ''
    contact.value = ''
    attachments.value = []
  } catch (e) {
    error.value = e instanceof Error ? e.message : '反馈提交失败，请稍后重试。'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page feedback-page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>意见反馈</h2>
    </header>

    <p class="page-sub">SEED FEEDBACK</p>

    <section class="card type-card">
      <div class="form-field">
        <label>反馈类型</label>
        <div class="chips">
          <button v-for="t in types" :key="t" type="button" class="chip" :class="{ selected: type === t }" @click="type = t">{{ t }}<span v-if="type === t" aria-hidden="true"> 🌸</span></button>
        </div>
      </div>
    </section>

    <section class="card content-card">
      <div class="form-field">
        <label>问题或建议描述</label>
        <textarea v-model="content" rows="5" placeholder="请在此处详细描述您遇到的问题或宝贵的改进建议，这能帮助我们更好地改善您的使用体验 🌿"></textarea>
      </div>
      <div class="form-field">
        <label>添加图片/截图 (选填，最多3张)</label>
        <label class="add-img"><span class="add-symbol">+</span><span>添加图片</span><input type="file" accept="image/*" multiple hidden @change="onFilesSelected" /></label>
        <p v-if="attachments.length" class="attachment-names">{{ attachments.join('、') }}</p>
      </div>
    </section>

    <section class="card contact-card">
      <div class="form-field">
        <label>联系方式 (选填)</label>
        <input v-model="contact" placeholder="留下您的手机号或邮箱，方便我们联系您" />
      </div>
    </section>

    <button class="btn-primary" :disabled="saving || !content.trim()" @click="submit">{{ saving ? '提交中…' : '提交反馈' }}</button>
    <p v-if="submitted" class="toast">感谢你的反馈！</p>
    <p v-if="error" class="error">{{ error }}</p>
    <p class="foot">提交后，我们将在24小时内尽快通过系统或您预留的联系方式与您回复，感谢支持 🌱</p>
  </div>
</template>

<style scoped>
.feedback-page { gap: var(--space-4); padding: var(--space-4) var(--space-5) var(--space-5); }
.feedback-page .page-head { position: relative; justify-content: center; }
.feedback-page .page-head .back { position: absolute; left: 0; }
.feedback-page .page-head h2 { font-size: var(--text-2xl); }
.feedback-page .page-sub { margin: calc(var(--space-1) * -1) 0 0; text-align: center; color: var(--brand); font-size: var(--text-md); font-weight: var(--weight-semibold); letter-spacing: 0.02em; }
.feedback-page .form-field { margin-bottom: 0; }
.feedback-page .form-field label { color: var(--text-primary); font-size: var(--text-md); font-weight: var(--weight-semibold); }
.type-card, .content-card, .contact-card { border: none; border-radius: var(--radius-2xl); box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.type-card { padding: var(--space-5) var(--space-6); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.chip { padding: var(--space-2) var(--space-4); border: 1px solid transparent; border-radius: var(--radius-full); background: #f7f6f3; color: var(--text-secondary); font: inherit; font-size: var(--text-md); cursor: pointer; }
.chip.selected { border-color: var(--brand); background: #edf5f0; color: var(--brand-strong); font-weight: var(--weight-semibold); }
.content-card { padding: var(--space-5) var(--space-6); }
.content-card .form-field:first-child { margin-bottom: var(--space-5); }
.feedback-page textarea { min-height: 148px; resize: vertical; background: var(--bg-page); border-color: transparent; border-radius: var(--radius-xl); line-height: 1.6; }
.feedback-page textarea::placeholder { color: var(--text-muted); }
.add-img { width: 90px; height: 90px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-1); border: 2px dashed var(--border); background: var(--bg-page); border-radius: var(--radius-lg); font-size: var(--text-xs); color: var(--text-muted); cursor: pointer; font-family: inherit; }
.add-symbol { font-size: 32px; line-height: 1; color: var(--text-secondary); font-weight: var(--weight-semibold); }
.toast { text-align: center; color: var(--brand-strong); font-size: var(--text-sm); }
.error { text-align: center; color: var(--accent-purple); font-size: var(--text-sm); }
.attachment-names { margin-top: var(--space-2); font-size: var(--text-xs); color: var(--text-muted); }
.contact-card { padding: var(--space-5) var(--space-6); }
.feedback-page .contact-card input { border-radius: var(--radius-lg); background: var(--bg-page); }
.feedback-page > .btn-primary { border-radius: var(--radius-full); padding: var(--space-4); box-shadow: 0 8px 18px rgba(111, 144, 125, 0.18); }
.foot { margin-top: calc(var(--space-2) * -1); text-align: center; font-size: var(--text-xs); color: var(--text-muted); line-height: 1.6; }
</style>
