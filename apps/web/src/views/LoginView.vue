<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login as apiLogin, register as apiRegister } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const nickname = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value.trim() || !password.value) return
  if (mode.value === 'register' && !nickname.value.trim()) {
    error.value = '请填写昵称'
    return
  }
  if (mode.value === 'register' && (!/^.{8,20}$/.test(password.value) || !/[A-Za-z]/.test(password.value) || !/\d/.test(password.value))) {
    error.value = '密码须为 8–20 位，并同时包含字母和数字'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = mode.value === 'login'
      ? await apiLogin(username.value.trim(), password.value)
      : await apiRegister(username.value.trim(), password.value, nickname.value.trim())
    auth.setAuth(res.token, res.user)
    router.push(res.user.onboarding_completed ? '/' : { path: '/interest-selection', query: { onboarding: '1' } })
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login">
    <div class="fern fern-tl" aria-hidden="true">
      <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" stroke-width="2" opacity="0.3">
        <path d="M6 82 C 24 57, 34 35, 63 18 C 76 10, 88 5, 98 2 C 101 25, 98 47, 86 62 C 67 85, 37 92, 6 82 Z" />
        <path d="M6 82 C 35 63, 59 39, 98 2" />
      </svg>
    </div>
    <div class="fern fern-br" aria-hidden="true">
      <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" stroke-width="2" opacity="0.3">
        <path d="M94 18 C 70 25, 47 38, 31 58 C 20 72, 14 88, 11 99 C 34 98, 57 91, 72 77 C 89 61, 95 40, 94 18 Z" />
        <path d="M11 99 C 36 73, 60 50, 94 18" />
      </svg>
    </div>

    <div class="login-body">
      <div class="sprout">
        <img src="/illustrations/login-sprout.png" alt="" />
      </div>
      <h1 class="brand">福小禾</h1>
      <p class="slogan">从一颗种子，长成复合型大树</p>

      <div class="form">
        <div class="input-row">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
          <input v-model="username" placeholder="请输入用户名" maxlength="50" />
        </div>

        <div v-if="mode === 'register'" class="input-row">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
            <line x1="9" y1="9" x2="9.01" y2="9"/>
            <line x1="15" y1="9" x2="15.01" y2="9"/>
          </svg>
          <input v-model="nickname" placeholder="请设置昵称" maxlength="50" />
        </div>

        <div class="input-row">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="11" width="18" height="11" rx="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
          <input v-model="password" type="password" placeholder="请输入密码（至少 8 位且包含字母和数字）" @keyup.enter="submit" />
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <button class="btn-primary login-btn" :disabled="loading || !username || !password" @click="submit">
          <span>{{ loading ? '请稍候…' : (mode === 'login' ? '登录' : '注册') }}</span>
          <span v-if="!loading" class="login-arrow">›</span>
        </button>

        <div class="mode-switch">
          <span>{{ mode === 'login' ? '还没有花园账号？' : '已经有花园账号？' }}</span>
          <button @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '注册账号' : '返回登录' }}
          </button>
        </div>
      </div>

      <p class="agreement">
        <span class="agreement-leaf" aria-hidden="true"><svg viewBox="0 0 32 18" fill="none"><path d="M2 13 C 9 3, 19 2, 29 3 C 24 12, 14 16, 2 13 Z"/><path d="M2 13 C 10 11, 18 7, 29 3"/></svg></span>
        <span>南京大学 · 三三制花园</span>
        <span class="agreement-leaf agreement-leaf-right" aria-hidden="true"><svg viewBox="0 0 32 18" fill="none"><path d="M30 13 C 23 3, 13 2, 3 3 C 8 12, 18 16, 30 13 Z"/><path d="M30 13 C 22 11, 14 7, 3 3"/></svg></span>
      </p>
    </div>
  </div>
</template>

<style scoped>
.login {
  position: relative;
  min-height: 100vh;
  background:
    radial-gradient(circle at 14% 34%, rgba(226, 239, 220, 0.6), transparent 28%),
    radial-gradient(circle at 88% 48%, rgba(236, 232, 244, 0.45), transparent 24%),
    #fbfcf8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.fern {
  position: absolute;
  color: var(--brand-strong);
}
.fern-tl { top: -30px; left: -44px; width: 198px; height: 198px; transform: rotate(-5deg); }
.fern-br { bottom: -6px; right: -44px; width: 198px; height: 198px; transform: rotate(0deg); }
.fern svg { width: 100%; height: 100%; opacity: 0.22; stroke-width: 1.3; }

.login-body {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 390px;
  min-height: 100vh;
  padding: clamp(72px, 15vh, 132px) var(--space-6) var(--space-8);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.sprout {
  width: 132px;
  height: 132px;
  color: var(--brand-strong);
  display: flex;
  align-items: center;
  justify-content: center;
}
.sprout img { width: 100%; height: 100%; object-fit: contain; }
.brand {
  margin-top: var(--space-4);
  font-size: 3.1rem;
  font-weight: var(--weight-extrabold);
  letter-spacing: 0.08em;
  color: #684b78;
}
.slogan {
  margin-top: var(--space-1);
  font-size: var(--text-lg);
  letter-spacing: 0.04em;
  color: #5a7a6b;
}

.form {
  width: 100%;
  margin-top: clamp(36px, 7vh, 58px);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.input-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: var(--bg-surface);
  min-height: 64px;
  border: 2px solid #dce8d2;
  border-radius: 999px;
  padding: var(--space-3) var(--space-5);
  color: #82a583;
  box-shadow: 0 5px 14px rgba(99, 128, 105, 0.04);
}
.input-row input {
  flex: 1;
  border: none;
  outline: none;
  font-size: var(--text-base);
  font-family: inherit;
  color: var(--text-primary);
  background: transparent;
}
.error {
  font-size: var(--text-xs);
  color: #dc2626;
  padding: 0 var(--space-2);
}
.login-btn {
  margin-top: var(--space-3);
  min-height: 62px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 14px;
  background: var(--brand-gradient);
  box-shadow: 0 12px 24px rgba(91, 126, 103, 0.22);
  font-size: var(--text-lg);
  letter-spacing: 0.08em;
}
.login-arrow { font-size: 2rem; line-height: 0.6; font-weight: 300; }
.mode-switch {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 6px;
  margin-top: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-muted);
}
.mode-switch button {
  border: 0;
  padding: 0;
  background: transparent;
  color: #684b78;
  font: inherit;
  font-weight: var(--weight-semibold);
  cursor: pointer;
}
.agreement {
  margin-top: var(--space-5);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-size: var(--text-xs);
  color: #999a91;
  letter-spacing: 0.08em;
  text-align: center;
}
.agreement-leaf { width: 30px; height: 18px; color: #86a989; display: inline-flex; }
.agreement-leaf svg { width: 100%; height: 100%; stroke: currentColor; stroke-width: 1.7; }
.agreement-leaf-right { transform: scaleX(-1); }

@media (max-height: 720px) {
  .login-body { padding-top: 48px; }
  .sprout { width: 104px; height: 104px; }
  .brand { font-size: 2.6rem; }
  .form { margin-top: 28px; }
}
</style>
