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
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>意见反馈</h2>
    </header>

    <p class="page-sub">SEED FEEDBACK</p>

    <section class="card">
      <div class="form-field">
        <label>反馈类型</label>
        <div class="chips">
          <button v-for="t in types" :key="t" class="chip" :class="{ selected: type === t }" @click="type = t">{{ t }}</button>
        </div>
      </div>
      <div class="form-field">
        <label>问题或建议描述</label>
        <textarea v-model="content" rows="5" placeholder="请在此处详细描述您遇到的问题或宝贵的改进建议，这能帮助我们更好地改善您的使用体验 🌿"></textarea>
      </div>
      <div class="form-field">
        <label>添加图片/截图 (选填，最多3张)</label>
        <label class="add-img">➕ 添加图片（最多 3 张）<input type="file" accept="image/*" multiple hidden @change="onFilesSelected" /></label>
        <p v-if="attachments.length" class="attachment-names">{{ attachments.join('、') }}</p>
      </div>
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
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.add-img { display: block; padding: var(--space-3); border: 1px dashed var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-muted); cursor: pointer; font-family: inherit; width: 100%; }
.toast { text-align: center; color: var(--brand-strong); font-size: var(--text-sm); }
.error { text-align: center; color: var(--accent-purple); font-size: var(--text-sm); }
.attachment-names { margin-top: var(--space-2); font-size: var(--text-xs); color: var(--text-muted); }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-muted); line-height: 1.6; }
</style>
