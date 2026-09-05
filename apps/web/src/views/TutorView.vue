<script setup lang="ts">
import { computed, ref } from 'vue'
import BackButton from '../components/BackButton.vue'

const mode = ref<'enrolled' | 'self_study'>('enrolled')
const selectedTopic = ref('数据分析')

const topics = [
  { name: '消息写作', state: 'done', position: 'writing' },
  { name: '数据可视化', state: 'mastered', position: 'visual' },
  { name: '数据分析', state: 'progress', position: 'analysis' },
  { name: '深度报道', state: 'progress', position: 'report' },
  { name: '采访 & 写作', state: 'mastered', position: 'interview' },
  { name: '数据新闻', state: 'done', position: 'data' },
  { name: '融合编辑', state: 'todo', position: 'editing' },
  { name: '新闻学概论', state: 'mastered', position: 'theory' },
]

const topicDetails: Record<string, string> = {
  '消息写作': '已完成基础阅读与练习，可以继续挑战真实新闻案例。',
  '数据可视化': '已掌握图表选择和信息表达，推荐复习可视化叙事。',
  '数据分析': '正在学习数据清洗和基础分析方法。',
  '深度报道': '正在积累选题、采访和证据组织能力。',
  '采访 & 写作': '已掌握采访提纲与稿件结构。',
  '数据新闻': '已完成数据新闻入门知识点。',
  '融合编辑': '尚未开始，建议先学习新闻学概论。',
  '新闻学概论': '已掌握新闻传播的基本概念和理论框架。',
}

const selectedDetail = computed(() => topicDetails[selectedTopic.value])

function selectTopic(name: string) {
  selectedTopic.value = name
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/" />
      <div>
        <h2>漫步知识森林 🌲</h2>
      </div>
    </header>

    <div class="mode-switch">
      <button :class="{ active: mode === 'enrolled' }" @click="mode = 'enrolled'">在校辅修小径</button>
      <button :class="{ active: mode === 'self_study' }" @click="mode = 'self_study'">独立自学小径</button>
    </div>

    <p class="mode-desc">{{ mode === 'enrolled' ? '结合主修教材做跨学科讲解，沿着辅修课程逐步成长' : '按你的兴趣整合自学资源，生成更灵活的知识路线' }}</p>
    <p class="tree-hint">点击叶片或花朵，查看知识点的学习资源 ☝️</p>

    <section class="card tree-card">
      <div class="tree-title-row">
        <h3>新闻传播学知识树</h3>
        <div class="legend">
          <span><i class="legend-dot done" />已完成</span>
          <span><i class="legend-dot mastered" />已掌握</span>
          <span><i class="legend-dot progress" />进行中</span>
        </div>
      </div>

      <div class="tree-canvas">
        <img src="/illustrations/knowledge-tree.png" alt="" />
        <button
          v-for="topic in topics"
          :key="topic.name"
          class="tree-node"
          :class="[topic.position, topic.state, { chosen: selectedTopic === topic.name }]"
          @click="selectTopic(topic.name)"
        >{{ topic.name }}</button>
      </div>

      <div class="topic-detail">
        <strong>{{ selectedTopic }}</strong>
        <span>{{ selectedDetail }}</span>
      </div>
    </section>

    <section class="card progress-card">
      <h3>学习生长进度 🌱</h3>
      <div class="growth-stages">
        <div v-for="stage in ['🌱', '🌿', '🍃', '🌸', '🌺']" :key="stage" class="stage">{{ stage }}</div>
      </div>
      <div class="growth-labels">
        <span>初萌</span><span>真叶</span><span class="current">攀爬</span><span>花苞</span><span>盛开</span>
      </div>
      <div class="progress-track"><span class="progress-fill" /><span class="progress-point" /></div>
      <div class="progress-number"><strong>45</strong><span>% 已完成</span></div>
    </section>

    <router-link to="/chat?source=tutor" class="qa-entry">🌿 想深入理解知识点？进入伴学问答</router-link>
  </div>
</template>

<style scoped>
.page-head { align-items: flex-start; }
.page-head > div { flex: 1; }
.mode-switch { display: flex; gap: var(--space-1); padding: 4px; margin-bottom: var(--space-2); border-radius: var(--radius-full); background: var(--bg-green-soft); }
.mode-switch button { flex: 1; padding: var(--space-2) var(--space-3); border: none; border-radius: var(--radius-full); background: transparent; color: var(--brand-strong); font: inherit; font-size: var(--text-sm); cursor: pointer; }
.mode-switch button.active { background: var(--bg-surface); font-weight: var(--weight-semibold); box-shadow: 0 1px 3px rgba(54, 82, 64, .08); }
.mode-desc, .tree-hint { margin: 0; text-align: center; color: var(--text-muted); font-size: var(--text-xs); }
.tree-hint { margin: var(--space-3) 0; color: var(--brand-strong); }
.tree-card { padding: var(--space-4); }
.tree-title-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.tree-title-row h3, .progress-card h3 { margin: 0; font-size: var(--text-lg); color: var(--text-primary); }
.legend { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--space-2); font-size: var(--text-2xs); color: var(--text-muted); }
.legend span { display: inline-flex; align-items: center; gap: 3px; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--border); }
.legend-dot.done { background: #7eb38d; }
.legend-dot.mastered { background: #ef9ca0; }
.legend-dot.progress { border: 2px solid #a7bea9; background: transparent; }
.tree-canvas { position: relative; min-height: 256px; margin-top: var(--space-3); overflow: hidden; border-radius: var(--radius-lg); background: #f5f8f2; }
.tree-canvas img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; opacity: .13; mix-blend-mode: multiply; pointer-events: none; }
.tree-node { position: absolute; z-index: 1; padding: 6px 10px; border: 1px solid transparent; border-radius: var(--radius-full); color: #fff; font: inherit; font-size: var(--text-xs); font-weight: var(--weight-semibold); cursor: pointer; box-shadow: 0 2px 5px rgba(73, 90, 71, .08); transition: transform .15s, box-shadow .15s; }
.tree-node:hover, .tree-node.chosen { transform: translateY(-2px); box-shadow: 0 4px 9px rgba(73, 90, 71, .16); }
.tree-node.done { background: #83b694; }
.tree-node.mastered { background: #9c7c60; }
.tree-node.progress { background: #8db5d9; }
.tree-node.todo { background: #f0d8d0; color: var(--text-primary); }
.tree-node.writing { left: 20%; top: 14%; }
.tree-node.visual { right: 17%; top: 15%; }
.tree-node.analysis { left: 39%; top: 28%; }
.tree-node.report { left: 8%; top: 43%; }
.tree-node.interview { right: 8%; top: 43%; }
.tree-node.data { left: 38%; top: 50%; }
.tree-node.editing { left: 14%; top: 67%; }
.tree-node.theory { right: 10%; top: 67%; }
.topic-detail { display: flex; align-items: baseline; gap: var(--space-2); margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid var(--bg-subtle); color: var(--text-secondary); font-size: var(--text-xs); line-height: 1.5; }
.topic-detail strong { color: var(--brand-strong); white-space: nowrap; }
.progress-card { margin-top: var(--space-4); }
.growth-stages, .growth-labels { display: flex; justify-content: space-between; align-items: center; }
.growth-stages { margin-top: var(--space-4); font-size: var(--text-xl); }
.stage { width: 28px; text-align: center; filter: saturate(.85); }
.growth-labels { margin-top: var(--space-1); color: var(--text-muted); font-size: var(--text-xs); }
.growth-labels .current { color: var(--brand-strong); font-weight: var(--weight-semibold); }
.progress-track { position: relative; height: 10px; margin-top: var(--space-4); border-radius: var(--radius-full); background: var(--bg-green-soft); }
.progress-fill { display: block; width: 45%; height: 100%; border-radius: inherit; background: var(--brand-gradient); }
.progress-point { position: absolute; top: 50%; left: 45%; width: 24px; height: 24px; border-radius: 50%; background: #5ba5e8; transform: translate(-50%, -50%); box-shadow: 0 2px 5px rgba(62, 132, 197, .25); }
.progress-number { display: flex; justify-content: center; align-items: baseline; gap: var(--space-2); margin-top: var(--space-4); color: var(--brand-strong); }
.progress-number strong { color: var(--text-primary); font-size: 48px; line-height: 1; }
.progress-number span { font-size: var(--text-lg); }
.qa-entry { display: block; margin: var(--space-4) 0; color: var(--brand-strong); font-size: var(--text-sm); text-align: center; text-decoration: none; }
@media (max-width: 430px) {
  .tree-title-row { align-items: flex-start; flex-direction: column; }
  .legend { justify-content: flex-start; }
  .tree-canvas { min-height: 242px; }
}
</style>
