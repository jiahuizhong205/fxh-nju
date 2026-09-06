import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { AuthUser } from '../api/client'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('fxh_token') || '')
  const user = ref<AuthUser | null>(JSON.parse(localStorage.getItem('fxh_user') || 'null'))
  const isAuthenticated = computed(() => !!token.value)

  function setAuth(newToken: string, newUser: AuthUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem('fxh_token', newToken)
    localStorage.setItem('fxh_user', JSON.stringify(newUser))
  }

  function clearAuth() {
    token.value = ''
    user.value = null
    localStorage.removeItem('fxh_token')
    localStorage.removeItem('fxh_user')
  }

  function setNickname(nickname: string) {
    if (user.value) {
      user.value = { ...user.value, nickname }
      localStorage.setItem('fxh_user', JSON.stringify(user.value))
    }
  }

  function setOnboardingCompleted(completed: boolean) {
    if (user.value) {
      user.value = { ...user.value, onboarding_completed: completed }
      localStorage.setItem('fxh_user', JSON.stringify(user.value))
    }
  }

  return { token, user, isAuthenticated, setAuth, clearAuth, setNickname, setOnboardingCompleted }
})
