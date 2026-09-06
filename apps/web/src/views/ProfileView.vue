<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, getFavoriteJobIds, logout, type StudentProfile } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useAvatarStore } from '../stores/avatar'
import BackButton from '../components/BackButton.vue'

const router = useRouter()
const auth = useAuthStore()
const avatarStore = useAvatarStore()
const profile = ref<StudentProfile | null>(null)
const loading = ref(true)
const favoriteCount = ref(0)

const displayName = computed(() => auth.user?.nickname || auth.user?.username || '园丁同学')
const profileSummary = computed(() => profile.value ? `${profile.value.major} · ${profile.value.grade}` : '完善画像后解锁更多成长记录')
const interestsSummary = computed(() => profile.value?.interests?.slice(0, 3).join(' · ') || '尚未填写兴趣方向')

// 学习进度接口尚未接入，先保留 Figma 中的前端展示占位。
const harvestedCredits = 28
const totalCredits = 50
const completionPercent = Math.round((harvestedCredits / totalCredits) * 100)

async function handleLogout() {
  try { await logout() } catch { /* token 已失效也照常退出 */ }
  avatarStore.reset()
  auth.clearAuth()
  router.push('/login')
}

onMounted(async () => {
  try {
    const [loadedProfile] = await Promise.all([fetchProfile(), avatarStore.load()])
    profile.value = loadedProfile
    favoriteCount.value = getFavoriteJobIds().length
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
})

</script>

<template>
  <div class="profile">
    <header class="profile-hero">
      <div class="hero-top">
        <BackButton fallback="/" />
      </div>
      <img class="avatar" :src="avatarStore.avatarUrl" alt="头像" />
      <h1>{{ displayName }} <span class="star">⭐</span></h1>
      <p class="major">{{ profileSummary }}</p>
      <p class="streak">你已经浇灌了 120 天的复合学习 🌻</p>
    </header>

    <section class="garden-card">
      <div class="section-title"><span>🍀</span><h2>我的花园</h2></div>

      <router-link to="/edit-profile" class="garden-row">
        <span class="row-icon">🌳</span>
        <span class="row-main">
          <span class="row-label">当前辅修专业</span>
          <strong>{{ profile?.major || '还没有选择专业' }}</strong>
          <span class="row-detail">{{ interestsSummary }}</span>
        </span>
        <span class="chevron">›</span>
      </router-link>

      <div class="garden-row progress-row">
        <span class="row-icon">🍒</span>
        <span class="row-main">
          <span class="row-label">已修学分进度</span>
          <strong>已收获 {{ harvestedCredits }}/{{ totalCredits }} 颗果实</strong>
        </span>
        <strong class="percent">{{ completionPercent }}%</strong>
        <span class="progress-track"><span :style="{ width: `${completionPercent}%` }" /></span>
      </div>

      <router-link to="/career" class="garden-row">
        <span class="row-icon">🛡️</span>
        <span class="row-main">
          <span class="row-label">收藏的岗位</span>
          <strong>{{ favoriteCount }} 个收藏岗位</strong>
        </span>
        <span class="chevron">›</span>
      </router-link>
    </section>

    <router-link to="/settings" class="settings-entry">
      <span class="entry-emoji">🛠️</span>
      <strong>设置</strong>
      <span class="chevron">›</span>
    </router-link>

    <button class="logout-btn" @click="handleLogout">🍂 退出花园</button>
  </div>
</template>

<style scoped>
.profile { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-4); }
.profile-hero { display: flex; flex-direction: column; align-items: center; text-align: center; }
.hero-top { align-self: stretch; display: flex; align-items: center; margin-bottom: var(--space-2); }
.avatar { width: 92px; height: 92px; border-radius: var(--radius-full); object-fit: cover; border: 3px solid var(--bg-green-soft); }
.profile-hero h1 { margin-top: var(--space-3); font-size: var(--text-xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.star { font-size: var(--text-lg); }
.major { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--accent-purple); font-weight: var(--weight-semibold); }
.streak { margin-top: var(--space-2); padding: 4px var(--space-3); border: 1px solid var(--bg-green-soft); border-radius: var(--radius-full); color: var(--brand-strong); font-size: var(--text-xs); background: var(--bg-green-faint); }
.garden-card, .tools-card, .settings-entry { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); }
.garden-card { padding: var(--space-4); }
.section-title { display: grid; grid-template-columns: 30px minmax(0, 1fr); column-gap: var(--space-3); align-items: center; color: var(--accent-purple); }
.section-title span { width: 30px; font-size: var(--text-xl); text-align: center; }
.section-title h2 { font-size: var(--text-base); font-weight: var(--weight-semibold); }
.garden-row { display: flex; align-items: center; gap: var(--space-3); min-width: 0; padding: var(--space-4) 0; border-bottom: 1px solid var(--bg-subtle); color: var(--text-primary); text-decoration: none; }
.garden-row:last-child { border-bottom: none; padding-bottom: 0; }
.row-icon { width: 30px; flex-shrink: 0; font-size: var(--text-xl); text-align: center; }
.row-main { min-width: 0; flex: 1; display: flex; flex-direction: column; gap: 3px; }
.row-label { color: var(--text-muted); font-size: var(--text-xs); }
.row-main strong { color: var(--text-primary); font-size: var(--text-base); font-weight: var(--weight-semibold); }
.row-detail { color: var(--text-muted); font-size: var(--text-xs); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chevron { flex-shrink: 0; color: var(--brand); font-size: 28px; line-height: 1; }
.progress-row { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; column-gap: var(--space-3); align-items: start; }
.progress-row .row-icon { grid-column: 1; grid-row: 1; align-self: center; }
.progress-row .row-main { grid-column: 2; grid-row: 1; }
.progress-row .percent { grid-column: 3; grid-row: 1; }
.progress-row .percent { align-self: end; margin-bottom: 1px; }
.progress-track { grid-column: 1 / 4; grid-row: 2; display: block; width: 100%; height: 10px; margin-top: var(--space-2); overflow: hidden; border-radius: var(--radius-full); background: var(--bg-green-faint); border: 1px solid var(--bg-green-soft); }
.progress-track span { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--brand), var(--brand-strong)); }
.percent { flex-shrink: 0; color: var(--brand-strong) !important; font-size: var(--text-base) !important; }
.settings-entry { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); color: var(--text-primary); text-decoration: none; }
.settings-entry strong { flex: 1; font-size: var(--text-base); }
.entry-emoji { font-size: var(--text-lg); flex-shrink: 0; line-height: 1; }
.logout-btn { align-self: center; padding: var(--space-2) var(--space-6); border: 1px solid var(--accent-purple); border-radius: var(--radius-full); background: var(--bg-surface); color: var(--accent-purple); font-family: inherit; font-size: var(--text-sm); cursor: pointer; }
</style>
