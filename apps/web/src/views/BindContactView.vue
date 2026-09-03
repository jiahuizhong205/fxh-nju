<script setup lang="ts">
import { ref } from 'vue'

const phone = ref('138****1234')
const email = ref('xiaolin@nju.edu.cn')
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/settings" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>绑定手机/邮箱</h2>
    </header>

    <p class="page-sub">花园联络方式 🌿</p>

    <section class="card" style="padding: 0; overflow: hidden;">
      <div class="contact-row">
        <span class="contact-icon">📱</span>
        <div class="contact-main">
          <div class="contact-label">手机号</div>
          <div class="contact-value">{{ phone }}</div>
        </div>
        <button class="change">更换</button>
      </div>
      <div class="contact-row">
        <span class="contact-icon">✉️</span>
        <div class="contact-main">
          <div class="contact-label">邮箱</div>
          <div class="contact-value">{{ email }}</div>
        </div>
        <button class="change">更换</button>
      </div>
    </section>

    <button class="btn-ghost">添加备用联系方式</button>
    <p class="foot">绑定后可接收岗位推送、政策更新等通知，也可用于找回花园密码 🍀</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.contact-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--bg-subtle); }
.contact-row:last-child { border-bottom: none; }
.contact-icon { font-size: var(--text-xl); flex-shrink: 0; }
.contact-main { flex: 1; }
.contact-label { font-size: var(--text-xs); color: var(--text-muted); }
.contact-value { margin-top: 2px; font-size: var(--text-base); color: var(--text-primary); font-weight: var(--weight-medium); }
.change { padding: var(--space-1) var(--space-3); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.btn-ghost { width: 100%; margin-top: var(--space-4); padding: var(--space-3); border: 1px dashed var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
