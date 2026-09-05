<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { changePassword } from '../api/client'
import { useAuthStore } from '../stores/auth'
import BackButton from '../components/BackButton.vue'

const router = useRouter()
const auth = useAuthStore()

const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const showOldPwd = ref(false)
const showNewPwd = ref(false)
const showConfirmPwd = ref(false)
const submitting = ref(false)
const error = ref('')
const success = ref(false)

const strength = computed(() => {
  const pwd = newPwd.value
  if (!pwd) return ''
  let score = 0
  if (pwd.length >= 8) score++
  if (/[a-zA-Z]/.test(pwd) && /\d/.test(pwd)) score++
  if (/[^a-zA-Z0-9]/.test(pwd)) score++
  return score <= 0 ? '弱' : score === 1 ? '中' : '强'
})

const strengthScore = computed(() => {
  const pwd = newPwd.value
  if (!pwd) return 0
  let score = 0
  if (pwd.length >= 8) score++
  if (/[a-zA-Z]/.test(pwd) && /\d/.test(pwd)) score++
  if (/[^a-zA-Z0-9]/.test(pwd)) score++
  return score
})

async function submit() {
  if (!oldPwd.value || !newPwd.value || newPwd.value !== confirmPwd.value) return
  submitting.value = true
  error.value = ''
  try {
    await changePassword(oldPwd.value, newPwd.value)
    success.value = true
    auth.clearAuth()
    setTimeout(() => router.push('/login'), 1500)
  } catch (e: any) {
    error.value = e.message
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="page password-page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <h2>修改密码</h2>
    </header>

    <p class="page-sub">换一把花园钥匙</p>

    <div class="illus"><img src="/illustrations/key-pot.png" alt="" /></div>

    <section class="card password-card">
      <div class="form-field">
        <label>当前密码</label>
        <div class="password-input">
          <input v-model="oldPwd" :type="showOldPwd ? 'text' : 'password'" placeholder="请输入当前密码" />
          <button type="button" class="eye" :aria-label="showOldPwd ? '隐藏当前密码' : '显示当前密码'" @click="showOldPwd = !showOldPwd"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.2-5 9.5-5 9.5 5 9.5 5-3.2 5-9.5 5-9.5-5-9.5-5Z" /><circle cx="12" cy="12" r="2.5" /></svg></button>
        </div>
      </div>
      <div class="form-field">
        <label>新密码</label>
        <div class="password-input">
          <input v-model="newPwd" :type="showNewPwd ? 'text' : 'password'" placeholder="请输入新密码" />
          <button type="button" class="eye" :aria-label="showNewPwd ? '隐藏新密码' : '显示新密码'" @click="showNewPwd = !showNewPwd"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.2-5 9.5-5 9.5 5 9.5 5-3.2 5-9.5 5-9.5-5-9.5-5Z" /><circle cx="12" cy="12" r="2.5" /></svg></button>
        </div>
      </div>
      <div class="form-field">
        <label>确认新密码</label>
        <div class="password-input">
          <input v-model="confirmPwd" :type="showConfirmPwd ? 'text' : 'password'" placeholder="请再次输入新密码" />
          <button type="button" class="eye" :aria-label="showConfirmPwd ? '隐藏确认密码' : '显示确认密码'" @click="showConfirmPwd = !showConfirmPwd"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.2-5 9.5-5 9.5 5 9.5 5-3.2 5-9.5 5-9.5-5-9.5-5Z" /><circle cx="12" cy="12" r="2.5" /></svg></button>
        </div>
      </div>
      <div class="strength">
        <span class="strength-label">密码强度：</span>
        <div class="strength-bars" aria-hidden="true"><span v-for="index in 3" :key="index" :class="{ filled: index <= strengthScore }" /></div>
        <span class="strength-value">{{ strength || '—' }}</span>
      </div>
    </section>

    <ul class="rules">
      <li>• 长度为8-20位</li>
      <li>• 包含字母和数字</li>
      <li>• 建议包含特殊字符更安全</li>
    </ul>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success">更换成功，请用新密码重新登录 🔐</p>

    <button class="btn-primary" :disabled="submitting || !oldPwd || !newPwd || newPwd !== confirmPwd" @click="submit">
      {{ submitting ? '请稍候…' : '确认更换钥匙' }}
    </button>
    <p class="foot">更换后，下次登录请使用新花园钥匙</p>
  </div>
</template>

<style scoped>
.password-page { gap: var(--space-4); padding: var(--space-4) var(--space-5) var(--space-5); }
.password-page .page-head { align-items: flex-start; }
.password-page .page-head h2 { font-size: var(--text-2xl); }
.password-page .page-sub { margin: calc(var(--space-1) * -1) 0 0 52px; color: var(--brand); font-size: var(--text-md); }
.illus { display: flex; justify-content: center; margin: calc(var(--space-2) * -1) 0 0; }
.illus img { width: 390px; max-width: 100%; height: 132px; object-fit: fill; }
.password-card { padding: var(--space-6); border: none; border-radius: var(--radius-2xl); box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.password-page .form-field { margin-bottom: var(--space-5); }
.password-page .form-field:last-of-type { margin-bottom: var(--space-3); }
.password-page .form-field label { color: var(--accent-purple); font-size: var(--text-md); font-weight: var(--weight-semibold); }
.password-input { position: relative; }
.password-input input { width: 100%; padding-right: 48px; border-radius: var(--radius-lg); }
.eye { position: absolute; top: 50%; right: var(--space-3); transform: translateY(-50%); padding: var(--space-1); border: none; background: transparent; color: var(--brand); cursor: pointer; line-height: 1; }
.eye svg { display: block; width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.strength { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); }
.strength-label { color: var(--text-muted); }
.strength-value { color: var(--brand-strong); font-weight: var(--weight-semibold); }
.strength-bars { display: flex; flex: 1; gap: var(--space-2); }
.strength-bars span { height: 7px; flex: 1; border-radius: var(--radius-full); background: var(--bg-subtle); }
.strength-bars span.filled { background: var(--brand); }
.rules { margin: calc(var(--space-2) * -1) var(--space-2) 0; list-style: none; }
.rules li { font-size: var(--text-xs); color: var(--text-muted); line-height: 1.8; }
.error { font-size: var(--text-xs); color: #dc2626; }
.success { font-size: var(--text-xs); color: #16a34a; }
.password-page > .btn-primary { border-radius: var(--radius-full); padding: var(--space-4); box-shadow: 0 8px 18px rgba(111, 144, 125, 0.18); }
.foot { text-align: center; font-size: var(--text-sm); color: var(--text-muted); }
</style>
