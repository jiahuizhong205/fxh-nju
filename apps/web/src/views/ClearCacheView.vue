<script setup lang="ts">
import { ref } from 'vue'

const items = ref([
  { label: '清理图片缓存', desc: '已缓存的政策文件图片、课程表截图', size: '180 MB' },
  { label: '清理对话记录', desc: '历史对话记录和问答缓存', size: '52 MB' },
  { label: '清理推荐报告缓存', desc: '已生成的辅修推荐报告临时文件', size: '24 MB' },
])

function clearItem(it: (typeof items.value)[number]) {
  it.size = '0 B'
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/settings" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>清除缓存</h2>
    </header>

    <p class="page-sub">扫走枯叶 🗑️</p>

    <section class="card cache-info">
      <img class="cache-illus" src="/illustrations/cache-clean.png" alt="" />
      <div class="cache-label">当前缓存大小</div>
      <div class="cache-size">256 MB</div>
      <p class="cache-desc">包含图片、政策文件、课表数据等</p>
    </section>

    <section class="card">
      <h4 class="card-title">深度清理细项</h4>
      <div class="item-list">
        <div v-for="it in items" :key="it.label" class="item">
          <div class="item-main">
            <div class="item-label">{{ it.label }}</div>
            <div class="item-desc">{{ it.desc }}</div>
          </div>
          <div class="item-right">
            <span class="item-size">{{ it.size }}</span>
            <button class="clear" @click="clearItem(it)">清理</button>
          </div>
        </div>
      </div>
    </section>

    <button class="btn-primary">一键清理所有缓存</button>
    <p class="foot">清理后不影响账号数据和已保存的课表规划 🍂</p>
  </div>
</template>

<style scoped>
.page-sub { font-size: var(--text-sm); color: var(--text-muted); margin-bottom: var(--space-2); }
.cache-info { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); padding: var(--space-8) var(--space-4); }
.cache-illus { width: 64px; height: 74px; margin-bottom: var(--space-2); }
.cache-label { font-size: var(--text-sm); color: var(--text-muted); }
.cache-size { font-size: var(--text-4xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.cache-desc { font-size: var(--text-xs); color: var(--text-muted); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.item-list { display: flex; flex-direction: column; gap: var(--space-3); }
.item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.item-main { flex: 1; }
.item-label { font-size: var(--text-sm); font-weight: var(--weight-medium); color: var(--text-primary); }
.item-desc { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.item-right { display: flex; align-items: center; gap: var(--space-3); }
.item-size { font-size: var(--text-sm); color: var(--text-secondary); }
.clear { padding: var(--space-1) var(--space-3); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-sm); font-size: var(--text-xs); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
