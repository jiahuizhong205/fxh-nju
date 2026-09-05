<script setup lang="ts">
import BackButton from '../components/BackButton.vue'

import { ref } from 'vue'

const items = ref([
  { label: '个人资料', time: '今天 14:32', synced: true },
  { label: '辅修推荐报告', time: '今天 10:15', synced: true },
  { label: '课程规划数据', time: '昨天 22:00', synced: true },
  { label: '岗位收藏', time: '未同步，点击同步', synced: false },
  { label: '学习进度', time: '今天 14:30', synced: true },
])

function syncItem(it: (typeof items.value)[number]) {
  it.synced = true
  it.time = '刚刚'
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <h2>数据同步状态</h2>
    </header>

    <p class="page-sub">种子备份云 ☁️</p>

    <div class="illus"><img src="/illustrations/data-sync.png" alt="" /></div>

    <section class="card">
      <div class="cloud-row">
        <div>
          <div class="cloud-label">云端同步状态</div>
          <div class="cloud-time">上次同步：今天 14:32</div>
        </div>
        <span class="cloud-ok">已同步 🌸</span>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">同步细项列表</h4>
      <div class="item-list">
        <div v-for="it in items" :key="it.label" class="item" @click="!it.synced && syncItem(it)">
          <div class="item-main">
            <div class="item-label">{{ it.label }}</div>
            <div class="item-time">{{ it.time }}</div>
          </div>
          <span class="item-status" :class="{ pending: !it.synced }">
            {{ it.synced ? '已同步 ✅' : '待同步 ⏳' }}
          </span>
        </div>
      </div>
    </section>

    <button class="btn-primary">🔄 手动同步所有数据</button>
    <button class="btn-ghost">☁️ 切换备份账号 / 云端存储</button>
    <p class="foot">当前备份至：icloud@nju.edu.cn</p>
    <p class="foot-sub">自动同步在Wi-Fi环境下每小时执行一次，流量环境下仅手动同步 🌿</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.illus { display: flex; justify-content: center; margin: var(--space-2) 0 var(--space-3); }
.illus img { width: 159px; height: 120px; }
.cloud-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.cloud-label { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--text-primary); }
.cloud-time { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.cloud-ok { font-size: var(--text-sm); color: var(--brand-strong); font-weight: var(--weight-semibold); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.item-list { display: flex; flex-direction: column; gap: var(--space-3); }
.item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); cursor: pointer; }
.item-label { font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--text-primary); }
.item-time { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.item-status { font-size: var(--text-xs); color: var(--brand-strong); white-space: nowrap; }
.item-status.pending { color: var(--accent-purple); }

.btn-ghost { width: 100%; margin-top: var(--space-3); padding: var(--space-3); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-secondary); }
.foot-sub { margin-top: var(--space-1); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
