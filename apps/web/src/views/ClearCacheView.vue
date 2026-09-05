<script setup lang="ts">
import { computed, ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const items = ref([
  { label: '清理图片缓存', desc: '已缓存的政策文件图片、课程表截图', size: 180, cleared: false },
  { label: '清理对话记录', desc: '历史对话记录和问答缓存', size: 52, cleared: false },
  { label: '清理推荐报告缓存', desc: '已生成的辅修推荐报告临时文件', size: 24, cleared: false },
])

const totalSize = computed(() => items.value.reduce((total, item) => total + (item.cleared ? 0 : item.size), 0))
const allCleared = computed(() => items.value.every(item => item.cleared))

function clearItem(item: (typeof items.value)[number]) {
  item.cleared = true
}

function clearAll() {
  items.value.forEach(item => { item.cleared = true })
}
</script>

<template>
  <div class="page clear-cache-page">
    <header class="page-head">
      <BackButton fallback="/settings" />
      <h2>清除缓存</h2>
    </header>

    <p class="page-sub">扫走枯叶</p>

    <div class="cache-hero">
      <img class="cache-illus" src="/illustrations/cache-clean.png" alt="" />
    </div>

    <section class="card cache-info">
      <div class="cache-icon" aria-hidden="true">🗑️</div>
      <div class="cache-summary">
        <div class="cache-label">当前缓存大小</div>
        <div class="cache-size">{{ totalSize }} MB</div>
        <p class="cache-desc">包含图片、政策文件、课表数据等</p>
      </div>
    </section>

    <section class="card cache-details">
      <h4 class="card-title">深度清理细项</h4>
      <div class="item-list">
        <div v-for="it in items" :key="it.label" class="item">
          <div class="item-main">
            <div class="item-label">{{ it.label }}</div>
            <div class="item-desc">{{ it.desc }}</div>
          </div>
          <div class="item-right">
            <span class="item-size">{{ it.cleared ? '0 MB' : `${it.size} MB` }}</span>
            <button class="clear" :disabled="it.cleared" @click="clearItem(it)">{{ it.cleared ? '已清理' : '清理' }}</button>
          </div>
        </div>
      </div>
    </section>

    <button class="btn-primary" :disabled="allCleared" @click="clearAll">一键清理所有缓存</button>
    <p class="foot">清理后不影响账号数据和已保存的课表规划 🍂</p>
  </div>
</template>

<style scoped>
.clear-cache-page { gap: var(--space-4); padding: var(--space-4) var(--space-5) var(--space-5); }
.clear-cache-page .page-head { position: relative; justify-content: center; }
.clear-cache-page .page-head .back { position: absolute; left: 0; }
.clear-cache-page .page-head h2 { font-size: var(--text-2xl); }
.clear-cache-page .page-sub { margin: calc(var(--space-1) * -1) 0 0; text-align: center; color: var(--brand); font-size: var(--text-md); font-weight: var(--weight-semibold); }
.cache-hero { display: flex; align-items: center; justify-content: center; min-height: 120px; }
.cache-illus { width: 72px; height: 84px; object-fit: contain; }
.cache-info { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-5) var(--space-6); border: none; box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.cache-icon { width: 54px; height: 54px; display: grid; place-items: center; flex-shrink: 0; border-radius: var(--radius-full); background: var(--bg-pink-soft); font-size: 24px; }
.cache-summary { min-width: 0; }
.cache-label { font-size: var(--text-sm); color: var(--text-muted); }
.cache-size { margin-top: 2px; font-size: var(--text-4xl); line-height: 1.1; font-weight: var(--weight-bold); color: var(--text-primary); }
.cache-desc { font-size: var(--text-xs); color: var(--text-muted); }

.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.cache-details { padding: var(--space-5) var(--space-6); border: none; box-shadow: 0 8px 22px rgba(81, 94, 76, 0.08); }
.item-list { display: flex; flex-direction: column; }
.item { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--bg-subtle); }
.item:first-child { padding-top: 0; }
.item:last-child { padding-bottom: 0; border-bottom: none; }
.item-main { flex: 1; }
.item-label { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.item-desc { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.item-right { display: flex; align-items: center; gap: var(--space-3); }
.item-size { font-size: var(--text-sm); color: var(--text-secondary); }
.clear { min-width: 58px; padding: var(--space-2) var(--space-3); border: none; background: var(--bg-pink-soft); border-radius: var(--radius-full); font-size: var(--text-sm); color: #bc9485; cursor: pointer; font-family: inherit; }
.clear:disabled { opacity: 0.65; cursor: default; }
.clear-cache-page > .btn-primary { border-radius: var(--radius-full); padding: var(--space-4); box-shadow: 0 8px 18px rgba(111, 144, 125, 0.18); }
.foot { margin-top: calc(var(--space-1) * -1); text-align: center; font-size: var(--text-xs); color: var(--text-muted); }
</style>
