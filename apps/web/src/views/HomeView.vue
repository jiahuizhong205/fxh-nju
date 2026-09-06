<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'
import { fetchProfile, recommendPrograms, type StudentProfile, type Recommendation } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useAvatarStore } from '../stores/avatar'

const auth = useAuthStore()
const avatarStore = useAvatarStore()
const router = useRouter()
const profile = ref<StudentProfile | null>(null)
const recommendations = ref<Recommendation[]>([])
const recIndex = ref(0)
const error = ref('')

const rec = computed(() => recommendations.value[recIndex.value] ?? null)

const displayName = computed(() => auth.user?.nickname || auth.user?.username || '同学')
const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})
const matchFlowers = computed(() => rec.value ? '🌼'.repeat(Math.max(1, Math.min(5, Math.round(rec.value.total_score * 5)))) : '')

const entries = [
  { to: '/chat', label: '政策答疑', icon: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>' },
  { to: '/recommend', label: '辅修推荐', icon: '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>' },
  { to: '/course-planning', label: '课程规划', icon: '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>' },
  { to: '/tutor', label: '伴学助手', icon: '<path d="M12 2a4 4 0 0 0-4 4c0 1.5.8 2.8 2 3.5V11H6a2 2 0 0 0-2 2v3a2 2 0 0 0 2 2h.5l1 3a1 1 0 0 0 .9.7h7.2a1 1 0 0 0 .9-.7l1-3H18a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2h-4V9.5c1.2-.7 2-2 2-3.5a4 4 0 0 0-4-4z"/>' },
  { to: '/career', label: '职业探索', icon: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="m8.5 11 1.5 1.5 3-3"/>' },
]

async function loadRecommendations() {
  try {
    recommendations.value = await recommendPrograms()
    recIndex.value = 0
  } catch (e) {
    error.value = e instanceof Error ? e.message : '推荐加载失败，请稍后重试。'
  }
}

function refreshRecommendation() {
  if (recommendations.value.length > 1) {
    recIndex.value = (recIndex.value + 1) % recommendations.value.length
  } else {
    void loadRecommendations()
  }
}

onMounted(async () => {
  try {
    const [loadedProfile] = await Promise.all([fetchProfile(), avatarStore.load()])
    profile.value = loadedProfile
    if (profile.value) await loadRecommendations()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '首页数据加载失败，请稍后重试。'
  }
})
</script>

<template>
  <div class="home">
    <section class="hero">
      <div class="hero-top">
        <img class="avatar" :src="avatarStore.avatarUrl" alt="头像" />
        <div class="hero-id">
          <div class="hero-name">{{ displayName }} <span class="star">⭐</span></div>
        </div>
        <button class="bell" aria-label="通知" @click="router.push('/settings/notification')">
          <Icon name="bell" :size="20" />
        </button>
      </div>
      <div class="greeting-card">
        <h2 class="greeting">{{ greeting }}，{{ displayName }} 🌿</h2>
        <p v-if="profile" class="garden-msg">今天你的花园阳光正好，温度适宜。你播下的“复合种子”正在长出新的嫩芽！</p>
        <p v-else class="garden-msg">先完善你的画像，让福小禾为你准备一片合适的成长土壤。</p>
      </div>
    </section>

    <section class="entries">
      <router-link v-for="e in entries" :key="e.to" :to="e.to" class="entry">
        <span class="entry-icon">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" v-html="e.icon"></svg>
        </span>
        <span class="entry-label">{{ e.label }}</span>
      </router-link>
    </section>

    <section class="rec-head">
      <h3>为你推荐 🍀</h3>
      <button class="refresh" @click="refreshRecommendation">换一批</button>
    </section>

    <section class="recommend-card" @click="router.push('/recommend')">
      <span class="rec-icon" aria-hidden="true">◌</span>
      <div class="rec-body">
        <div class="rec-title-row">
          <h4>{{ rec ? `今日花园推荐：${rec.program.name}辅修` : '探索你的辅修方向' }}</h4>
        </div>
        <p v-if="rec" class="match-line">{{ matchFlowers }} <span>匹配度 {{ (rec.total_score * 100).toFixed(0) }}%</span></p>
        <p class="rec-desc">{{ rec ? `${rec.program.discipline} · ${rec.program.core_courses.slice(0, 3).join('、')}` : '先填写画像，让福小禾为你推荐最适合复合生长的方向。' }}</p>
        <div class="rec-divider"></div>
        <div class="rec-foot">
          <span class="rec-count">{{ rec ? `已有 ${rec.program.participant_count} 名种子同学加入该方向 · 需修 ${rec.program.total_credits} 学分` : '完善画像后查看方向热度' }}</span>
          <span class="rec-go">去瞧瞧 <b>›</b></span>
        </div>
      </div>
    </section>
    <p v-if="error" class="error-msg">{{ error }}</p>
  </div>
</template>

<style scoped>
.home {
  padding: var(--space-4) var(--space-4) var(--space-8);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.hero { display: flex; flex-direction: column; gap: var(--space-3); }
.hero-top { display: flex; align-items: center; gap: var(--space-3); }
.avatar {
  width: 52px; height: 52px; border-radius: var(--radius-full);
  object-fit: cover; flex-shrink: 0;
}
.hero-id { flex: 1; }
.hero-name { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); }
.star { font-size: var(--text-sm); }
.hero-num { margin-top: 2px; font-size: var(--text-xs); color: var(--text-muted); }
.bell {
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-full); width: 40px; height: 40px;
  display: flex; align-items: center; justify-content: center;
  color: var(--text-secondary); cursor: pointer; flex-shrink: 0;
}
.greeting-card { padding: var(--space-4); border: 1px solid var(--bg-green-soft); border-radius: var(--radius-xl); background: var(--bg-green-faint); }
.greeting { font-size: var(--text-xl); font-weight: var(--weight-bold); color: var(--brand-strong); }
.garden-msg { margin-top: var(--space-2); font-size: var(--text-base); color: var(--text-primary); line-height: 1.6; }

.entries {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--space-2);
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--space-3) var(--space-2);
}
.entry { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); text-decoration: none; color: var(--text-secondary); }
.entry-icon {
  width: 48px; height: 48px; border-radius: var(--radius-full);
  background: var(--bg-green-faint); display: flex; align-items: center; justify-content: center; color: var(--brand-strong);
}
.entry:nth-child(1) .entry-icon, .entry:nth-child(4) .entry-icon { background: var(--bg-pink-soft); }
.entry:nth-child(3) .entry-icon { background: var(--accent-purple-soft); color: var(--accent-purple); }
.entry-label { font-size: var(--text-xs); color: var(--text-secondary); white-space: nowrap; }

.rec-head { display: flex; justify-content: space-between; align-items: center; }
.rec-head h3 { font-size: var(--text-lg); font-weight: var(--weight-semibold); color: var(--text-primary); }
.refresh { border: none; background: none; color: var(--brand-strong); font-size: var(--text-sm); cursor: pointer; font-family: inherit; }

.recommend-card {
  position: relative; display: flex; gap: var(--space-3); padding: var(--space-5);
  background: var(--bg-surface); color: var(--text-primary); border: 1px solid var(--border);
  border-radius: var(--radius-xl); cursor: pointer; box-shadow: 0 5px 16px rgba(47, 59, 53, 0.04);
}
.rec-icon { width: 32px; height: 32px; flex: 0 0 32px; display: flex; align-items: center; justify-content: center; border-radius: var(--radius-full); background: var(--bg-green-faint); color: var(--brand); font-size: 25px; line-height: 1; }
.rec-body { min-width: 0; flex: 1; }
.rec-title-row { display: flex; justify-content: space-between; align-items: center; gap: var(--space-3); }
.rec-title-row h4 { font-size: var(--text-lg); font-weight: var(--weight-semibold); color: var(--text-primary); }
.match-line { margin-top: var(--space-2); color: var(--brand); font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.match-line span { margin-left: var(--space-2); }
.rec-desc { margin-top: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary); line-height: 1.6; }
.rec-divider { height: 1px; margin: var(--space-4) 0 var(--space-3); background: var(--bg-subtle); }
.rec-foot { display: flex; justify-content: space-between; align-items: center; }
.rec-count { max-width: 72%; font-size: var(--text-xs); line-height: 1.5; color: var(--text-muted); }
.rec-go { color: var(--brand); font-size: var(--text-sm); font-weight: var(--weight-semibold); }
.rec-go b { margin-left: 2px; font-size: var(--text-lg); line-height: 0; }
.error-msg { color: var(--accent-purple); font-size: var(--text-sm); }
</style>
