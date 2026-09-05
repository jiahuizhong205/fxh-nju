<script setup lang="ts">
import { useRouter } from 'vue-router'

const props = withDefaults(defineProps<{ fallback?: string }>(), {
  fallback: '/',
})

const router = useRouter()

function goBack() {
  const previous = window.history.state?.back
  if (typeof previous === 'string' && previous.startsWith('/')) {
    router.back()
    return
  }
  router.push(props.fallback)
}
</script>

<template>
  <button class="back" aria-label="返回上一页" type="button" @click="goBack">
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path d="m15 18-6-6 6-6" />
    </svg>
  </button>
</template>

<style scoped>
.back {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
}

.back svg {
  display: block;
}
</style>
