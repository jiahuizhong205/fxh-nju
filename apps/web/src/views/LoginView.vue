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
  loading.value = true
  error.value = ''
  try {
    const res = mode.value === 'login'
      ? await apiLogin(username.value.trim(), password.value)
      : await apiRegister(username.value.trim(), password.value, nickname.value.trim())
    auth.setAuth(res.token, res.user)
    router.push('/')
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
        <path d="M10 90 C 20 60, 15 40, 10 10" />
        <path d="M10 70 C 30 65, 45 60, 60 55" />
        <path d="M10 55 C 30 50, 45 45, 58 40" />
        <path d="M10 40 C 28 38, 42 34, 52 28" />
        <path d="M10 70 C -5 62, -12 55, -18 45" />
        <path d="M10 55 C -2 50, -8 44, -12 36" />
      </svg>
    </div>
    <div class="fern fern-br" aria-hidden="true">
      <svg viewBox="0 0 100 100" fill="none" stroke="currentColor" stroke-width="2" opacity="0.3">
        <path d="M90 10 C 80 40, 85 60, 90 90" />
        <path d="M90 30 C 70 35, 55 40, 40 45" />
        <path d="M90 45 C 70 50, 55 55, 42 60" />
        <path d="M90 60 C 72 62, 58 66, 48 72" />
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
          <input v-model="password" type="password" placeholder="请输入密码（至少 6 位）" @keyup.enter="submit" />
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

      <p class="agreement">南京大学 · 三三制花园</p>
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
.fern-tl { top: -26px; left: -28px; width: 176px; height: 176px; transform: rotate(-8deg); }
.fern-br { bottom: -28px; right: -30px; width: 176px; height: 176px; transform: rotate(172deg); }
.fern svg { opacity: 0.22; stroke-width: 1.4; }

.login-body {
  position: relative;
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
  background: linear-gradient(105deg, #82b58e, #5f8271);
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
  font-size: var(--text-xs);
  color: #999a91;
  letter-spacing: 0.08em;
  text-align: center;
}

@media (max-height: 720px) {
  .login-body { padding-top: 48px; }
  .sprout { width: 104px; height: 104px; }
  .brand { font-size: 2.6rem; }
  .form { margin-top: 28px; }
}
</style>
