<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { changePassword } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
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
  <div class="page">
    <header class="page-head">
      <router-link to="/profile" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>修改密码</h2>
    </header>

    <p class="page-sub">换一把花园钥匙</p>

    <div class="illus"><img src="/illustrations/key-pot.png" alt="" /></div>

    <section class="card">
      <div class="form-field">
        <label>当前密码</label>
        <input v-model="oldPwd" type="password" placeholder="••••••••" />
      </div>
      <div class="form-field">
        <label>新密码</label>
        <input v-model="newPwd" type="password" placeholder="••••••••" />
      </div>
      <div class="form-field">
        <label>确认新密码</label>
        <input v-model="confirmPwd" type="password" placeholder="••••••••" />
      </div>
      <div class="strength">
        <span class="strength-label">密码强度：</span>
        <span class="strength-value">{{ strength || '—' }}</span>
      </div>
      <ul class="rules">
        <li>• 长度为8-20位</li>
        <li>• 包含字母和数字</li>
        <li>• 建议包含特殊字符更安全</li>
      </ul>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="success" class="success">更换成功，请用新密码重新登录 🔐</p>

    <button class="btn-primary" :disabled="submitting || !oldPwd || !newPwd || newPwd !== confirmPwd" @click="submit">
      {{ submitting ? '请稍候…' : '确认更换钥匙' }}
    </button>
    <p class="foot">更换后，下次登录请使用新花园钥匙</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 100%; max-width: 390px; height: auto; }
.strength { margin-top: var(--space-3); display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); }
.strength-label { color: var(--text-muted); }
.strength-value { color: var(--brand-strong); font-weight: var(--weight-semibold); }
.rules { margin-top: var(--space-2); list-style: none; }
.rules li { font-size: var(--text-xs); color: var(--text-muted); line-height: 1.8; }
.error { font-size: var(--text-xs); color: #dc2626; }
.success { font-size: var(--text-xs); color: #16a34a; }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
