<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <div class="mark">🌱</div>
    <h2>这片花园还没有路</h2>
    <p>页面可能已经移动，或地址暂时不存在。</p>
    <button class="btn-primary" @click="router.push('/')">返回花园</button>
  </div>
</template>

<style scoped>
.not-found { min-height: 60vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-3); padding: var(--space-6); text-align: center; }
.mark { font-size: 3rem; }
h2 { color: var(--text-primary); font-size: var(--text-xl); }
p { color: var(--text-muted); font-size: var(--text-sm); }
.btn-primary { margin-top: var(--space-2); border: 0; cursor: pointer; }
</style>
