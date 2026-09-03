<script setup lang="ts">
import { ref } from 'vue'

const type = ref('功能建议')
const content = ref('')
const contact = ref('')
const submitted = ref(false)

const types = ['功能建议', 'Bug反馈', '体验问题', '其他']

function submit() {
  if (!content.value.trim()) return
  submitted.value = true
  setTimeout(() => (submitted.value = false), 3000)
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/settings" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
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
        <button class="add-img">➕ 添加图片</button>
      </div>
      <div class="form-field">
        <label>联系方式 (选填)</label>
        <input v-model="contact" placeholder="留下您的手机号或邮箱，方便我们联系您" />
      </div>
    </section>

    <button class="btn-primary" :disabled="!content.trim()" @click="submit">提交反馈</button>
    <p v-if="submitted" class="toast">感谢你的反馈！</p>
    <p class="foot">提交后，我们将在24小时内尽快通过系统或您预留的联系方式与您回复，感谢支持 🌱</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.add-img { padding: var(--space-3); border: 1px dashed var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-muted); cursor: pointer; font-family: inherit; width: 100%; }
.toast { text-align: center; color: var(--brand-strong); font-size: var(--text-sm); }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-muted); line-height: 1.6; }
</style>
