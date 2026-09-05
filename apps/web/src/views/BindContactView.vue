<script setup lang="ts">
import { ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const phone = ref('138****1234')
const email = ref('xiaolin@nju.edu.cn')
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>绑定手机/邮箱</h2>
    </header>

    <p class="page-sub">花园联络方式 🌿</p>

    <section class="contact-list">
      <div class="contact-card">
        <span class="contact-icon phone-icon">📱</span>
        <div class="contact-main">
          <div class="contact-label">手机号</div>
          <div class="contact-value">{{ phone }}</div>
        </div>
        <button class="change">更换</button>
      </div>
      <div class="contact-card">
        <span class="contact-icon email-icon">✉️</span>
        <div class="contact-main">
          <div class="contact-label">邮箱</div>
          <div class="contact-value">{{ email }}</div>
        </div>
        <button class="change">更换</button>
      </div>
    </section>

    <button class="btn-ghost">＋&nbsp; 添加备用联系方式</button>
    <p class="foot">绑定后可接收岗位推送、政策更新等通知，也可用于找回花园密码 🍀</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.contact-list { display: flex; flex-direction: column; gap: var(--space-4); }
.contact-card { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); background: var(--bg-surface); border: 1px solid var(--bg-green-soft); border-radius: var(--radius-lg); }
.contact-icon { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-full); font-size: var(--text-xl); flex-shrink: 0; }
.phone-icon { background: var(--bg-pink-soft); }
.email-icon { background: var(--bg-green-faint); }
.contact-main { flex: 1; }
.contact-label { font-size: var(--text-xs); color: var(--text-muted); }
.contact-value { margin-top: 2px; font-size: var(--text-base); color: var(--text-primary); font-weight: var(--weight-medium); }
.change { padding: var(--space-2) var(--space-3); border: none; background: var(--bg-green-faint); border-radius: var(--radius-full); font-size: var(--text-xs); font-weight: var(--weight-semibold); color: var(--brand-strong); cursor: pointer; font-family: inherit; }
.btn-ghost { width: 100%; margin-top: var(--space-4); padding: var(--space-3); border: 1px solid var(--brand); background: transparent; border-radius: var(--radius-full); font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--brand-strong); cursor: pointer; font-family: inherit; }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
