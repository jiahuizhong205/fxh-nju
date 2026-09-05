<script setup lang="ts">
import BackButton from '../components/BackButton.vue'

import { computed, ref } from 'vue'

const items = ref([
  { label: '个人资料', time: '今天 14:32', synced: true },
  { label: '辅修推荐报告', time: '今天 10:15', synced: true },
  { label: '课程规划数据', time: '昨天 22:00', synced: true },
  { label: '岗位收藏', time: '未同步，点击同步', synced: false },
  { label: '学习进度', time: '今天 14:30', synced: true },
])
const lastSync = ref('今天 14:32')
const allSynced = computed(() => items.value.every(item => item.synced))

function syncItem(it: (typeof items.value)[number]) {
  it.synced = true
  it.time = '刚刚'
  lastSync.value = '刚刚'
}

function syncAll() {
  items.value.forEach(item => {
    item.synced = true
    item.time = '刚刚'
  })
  lastSync.value = '刚刚'
}
</script>

<template>
  <div class="page sync-page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <h2>数据同步状态</h2>
    </header>

    <p class="page-sub">种子备份云</p>

    <div class="illus"><img src="/illustrations/data-sync.png" alt="数据同步插画" /></div>

    <section class="card cloud-card">
      <div class="cloud-row">
        <div class="cloud-icon" aria-hidden="true">☁️</div>
        <div class="cloud-copy">
          <div class="cloud-label">云端同步状态</div>
          <div class="cloud-time">上次同步：{{ lastSync }}</div>
        </div>
        <span class="cloud-ok">已同步 🌸</span>
      </div>
    </section>

    <section class="card sync-details">
      <h4 class="card-title">同步细项列表</h4>
      <div class="item-list">
        <button v-for="it in items" :key="it.label" type="button" class="item" :class="{ pending: !it.synced }" @click="!it.synced && syncItem(it)">
          <div class="item-main">
            <div class="item-label">{{ it.label }}</div>
          </div>
          <div class="item-right">
            <span class="item-status" :class="{ pending: !it.synced }">{{ it.synced ? '已同步 ✅' : '待同步 ⏳' }}</span>
            <span class="item-time">{{ it.time }}</span>
          </div>
        </button>
      </div>
    </section>

    <button class="btn-primary sync-all" :disabled="allSynced" @click="syncAll">🔄 手动同步所有数据</button>
    <button class="btn-ghost">☁️ 切换备份账号 / 云端存储</button>
    <p class="foot">当前备份至：icloud@nju.edu.cn</p>
    <p class="foot-sub">自动同步在Wi-Fi环境下每小时执行一次，流量环境下仅手动同步 🌿</p>
  </div>
</template>

<style scoped>
.sync-page { gap: var(--space-4); padding: var(--space-4) var(--space-5) var(--space-5); }
.sync-page .page-head { position: relative; justify-content: center; }
.sync-page .page-head .back { position: absolute; left: 0; }
.sync-page .page-head h2 { font-size: var(--text-2xl); }
.sync-page .page-sub { margin: calc(var(--space-1) * -1) 0 0; text-align: center; color: var(--brand); font-size: var(--text-md); font-weight: var(--weight-semibold); }
.illus { display: flex; justify-content: center; min-height: 142px; align-items: center; }
.illus img { width: 200px; height: 150px; object-fit: contain; }
.cloud-card { padding: var(--space-5) var(--space-6); border: none; border-radius: var(--radius-2xl); box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.cloud-row { display: flex; align-items: center; gap: var(--space-4); }
.cloud-icon { width: 56px; height: 56px; display: grid; place-items: center; flex-shrink: 0; border-radius: var(--radius-full); background: #edf5f0; font-size: 23px; }
.cloud-copy { flex: 1; min-width: 0; }
.cloud-label { font-size: var(--text-sm); font-weight: var(--weight-semibold); color: var(--text-primary); }
.cloud-time { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.cloud-ok { font-size: var(--text-sm); color: var(--brand-strong); font-weight: var(--weight-semibold); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.sync-details { padding: var(--space-5) var(--space-6); border: none; border-radius: var(--radius-2xl); box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.item-list { display: flex; flex-direction: column; }
.item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); width: 100%; padding: var(--space-3) 0; border: none; border-bottom: 1px solid var(--bg-subtle); background: transparent; color: inherit; cursor: default; font: inherit; text-align: left; }
.item:first-child { padding-top: 0; }
.item:last-child { padding-bottom: 0; border-bottom: none; }
.item.pending { cursor: pointer; }
.item-main { min-width: 0; }
.item-label { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.item-right { display: flex; align-items: center; gap: var(--space-3); flex-shrink: 0; }
.item-status { font-size: var(--text-xs); color: var(--brand-strong); white-space: nowrap; }
.item-status.pending { color: var(--accent-purple); }
.item-time { font-size: var(--text-xs); color: var(--text-muted); white-space: nowrap; }

.sync-all { border-radius: var(--radius-full); padding: var(--space-4); box-shadow: 0 8px 18px rgba(111, 144, 125, 0.18); }
.btn-ghost { width: 100%; margin-top: calc(var(--space-2) * -1); padding: var(--space-3); border: 1px solid var(--border); background: transparent; border-radius: var(--radius-full); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.foot { margin-top: var(--space-3); text-align: center; font-size: var(--text-xs); color: var(--text-secondary); }
.foot-sub { margin-top: var(--space-1); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
