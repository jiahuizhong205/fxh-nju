<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app">
    <header class="app-header">
      <h1>福小禾</h1>
      <span class="subtitle">南大复合型人才学习助手</span>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
  background: #f5f7fa;
  color: #1a1a2e;
}

.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 900px;
  margin: 0 auto;
}

.app-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #5b21b6, #7c3aed);
  color: #fff;
  flex-shrink: 0;
}

.app-header h1 {
  font-size: 1.4rem;
  font-weight: 700;
}

.app-header .subtitle {
  font-size: 0.85rem;
  opacity: 0.85;
}

.app-main {
  flex: 1;
  overflow: hidden;
  display: flex;
}
</style>
