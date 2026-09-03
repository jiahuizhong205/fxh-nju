<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, logout, type StudentProfile } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const profile = ref<StudentProfile | null>(null)
const loading = ref(true)

const certLabel: Record<string, string> = { degree: '辅修学位', cert: '结业证书', none: '仅旁听' }

onMounted(async () => {
  try {
    profile.value = await fetchProfile()
  } catch {
    profile.value = null
  } finally {
    loading.value = false
  }
})

async function handleLogout() {
  try { await logout() } catch { /* token 已失效也照常退出 */ }
  auth.clearAuth()
  router.push('/login')
}

const menu = [
  { label: '我的学习进度', to: '/settings/learning-progress', icon: '👀', desc: '谁可以逛我的花园' },
  { label: '修改密码', to: '/settings/change-password', icon: '🔐', desc: '换一把花园钥匙' },
  { label: '通知设置', to: '/settings/notification', icon: '🌸', desc: '风铃要响几声？' },
  { label: '数据同步', to: '/settings/data-sync', icon: '☁️', desc: '种子备份云' },
  { label: '设置', to: '/settings', icon: '⚙️', desc: '花园工具箱' },
]
</script>

<template>
  <div class="profile">
    <section class="user-card">
      <img class="avatar" src="/illustrations/avatar-wreath.png" alt="头像" />
      <div class="user-info">
        <h2>{{ auth.user?.nickname || auth.user?.username }} <span class="star">⭐</span></h2>
        <p class="account">@{{ auth.user?.username }}</p>
        <template v-if="loading">
          <p class="account">加载中…</p>
        </template>
        <template v-else-if="profile">
          <p>{{ profile.major }} · {{ profile.grade }} · {{ profile.campus }}</p>
        </template>
        <router-link v-else to="/edit-profile" class="empty-cta">完善园丁卡片，解锁推荐 →</router-link>
      </div>
      <router-link to="/edit-profile" class="edit-btn" aria-label="编辑个人资料">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
        </svg>
      </router-link>
    </section>

    <section v-if="profile" class="garden">
      <div class="garden-title">我的画像 🌳</div>
      <div class="garden-grid">
        <div class="garden-item">
          <span class="k">兴趣方向</span>
          <span class="v">{{ profile.interests.length ? profile.interests.join('、') : '未填写' }}</span>
        </div>
        <div class="garden-item">
          <span class="k">擅长技能</span>
          <span class="v">{{ profile.strengths.length ? profile.strengths.join('、') : '未填写' }}</span>
        </div>
        <div class="garden-item">
          <span class="k">职业目标</span>
          <span class="v">{{ profile.career_goals || '未填写' }}</span>
        </div>
        <div class="garden-item">
          <span class="k">证书目标</span>
          <span class="v">{{ certLabel[profile.certificate_goal] || '未填写' }}</span>
        </div>
      </div>
    </section>

    <section class="menu">
      <router-link v-for="m in menu" :key="m.to" :to="m.to" class="entry">
        <span class="entry-emoji">{{ m.icon }}</span>
        <span class="entry-main">
          <span class="entry-label">{{ m.label }}</span>
          <span class="entry-desc">{{ m.desc }}</span>
        </span>
        <svg class="chevron" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      </router-link>
      <button class="entry entry-logout" @click="handleLogout">
        <span class="entry-emoji">🍂</span>
        <span class="entry-main">
          <span class="entry-label">退出花园</span>
        </span>
      </button>
    </section>
  </div>
</template>

<style scoped>
.profile { padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-5); }

.user-card {
  display: flex; align-items: center; gap: var(--space-4);
  background: var(--bg-surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); padding: var(--space-5) var(--space-4);
}
.avatar {
  width: 72px; height: 72px; border-radius: var(--radius-full);
  object-fit: cover; flex-shrink: 0;
}
.user-info { flex: 1; }
.user-info .account { margin: 0; font-size: var(--text-xs); color: var(--text-muted); }
.user-info h2 { font-size: var(--text-xl); font-weight: var(--weight-bold); color: var(--text-primary); }
.star { font-size: var(--text-base); }
.user-info p { margin-top: var(--space-1); font-size: var(--text-sm); color: var(--text-muted); }
.empty-cta { display: inline-block; margin-top: var(--space-1); font-size: var(--text-sm); color: var(--brand-strong); font-weight: var(--weight-medium); text-decoration: none; }
.edit-btn {
  width: 36px; height: 36px; border-radius: var(--radius-full);
  background: var(--bg-green-faint); color: var(--brand-strong);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  text-decoration: none;
}

.garden { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-4); }
.garden-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.garden-grid { display: flex; flex-direction: column; gap: var(--space-4); }
.garden-item { display: flex; flex-direction: column; gap: 4px; }
.garden-item .k { font-size: var(--text-xs); color: var(--text-muted); }
.garden-item .v { font-size: var(--text-sm); color: var(--text-primary); font-weight: var(--weight-medium); line-height: 1.5; }

.menu { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); overflow: hidden; }
.entry {
  display: flex; align-items: center; gap: var(--space-3);
  width: 100%; padding: var(--space-4);
  text-decoration: none; color: var(--text-primary);
  border: none; border-bottom: 1px solid var(--bg-subtle);
  background: none; font-family: inherit; font-size: var(--text-base);
  cursor: pointer; text-align: left;
}
.entry:last-child { border-bottom: none; }
.entry-emoji { font-size: var(--text-lg); flex-shrink: 0; line-height: 1; }
.entry-main { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.entry-label { font-size: var(--text-base); font-weight: var(--weight-medium); }
.entry-desc { font-size: var(--text-xs); color: var(--text-muted); }
.chevron { color: var(--text-muted); flex-shrink: 0; }
.entry-logout { color: var(--accent-purple); }
</style>
