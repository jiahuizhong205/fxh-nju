<script setup lang="ts">
import { RouterView, useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

function isActive(path: string) {
  return route.path === path
}
</script>

<template>
  <div class="app">
    <header class="app-header">
      <h1>福小禾</h1>
      <span class="subtitle">南大复合型人才学习助手</span>
      <nav class="nav-links">
        <router-link to="/" :class="{ active: isActive('/') }">对话</router-link>
        <router-link to="/profile" :class="{ active: isActive('/profile') }">画像</router-link>
        <router-link to="/recommend" :class="{ active: isActive('/recommend') }">推荐</router-link>
        <router-link to="/tutor" :class="{ active: isActive('/tutor') }">伴学</router-link>
        <router-link to="/career" :class="{ active: isActive('/career') }">职业</router-link>
        <router-link to="/knowledge" :class="{ active: isActive('/knowledge') }">知识库</router-link>
      </nav>
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
  flex: 1;
}

.nav-links {
  display: flex; gap: 4px;
}
.nav-links a {
  color: rgba(255,255,255,0.75); text-decoration: none;
  padding: 4px 14px; border-radius: 16px; font-size: 0.85rem;
  transition: background 0.15s;
}
.nav-links a:hover, .nav-links a.active {
  background: rgba(255,255,255,0.2); color: #fff;
}

.app-main {
  flex: 1;
  overflow: hidden;
  display: flex;
}
</style>
