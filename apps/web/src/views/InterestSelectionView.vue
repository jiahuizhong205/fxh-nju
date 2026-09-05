<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, updateProfile } from '../api/client'
import BackButton from '../components/BackButton.vue'

const router = useRouter()

const majors = ['计算机科学', '新闻传播学', '经济学', '数学', '哲学']
const major = ref('计算机科学')

const interestOptions = ['数据分析', '写作创作', '商业策划', '人文哲思', '硬核科技', '设计艺术']
const interests = ref<string[]>(['写作创作', '数据分析'])

const strengthOptions = ['逻辑推理', '沟通表达', '创意思维', '数据处理', '动手实验', '组织协调', '外语能力', '编程基础', '其他']
const strengths = ref<string[]>(['逻辑推理', '创意思维'])

function toggle(list: string[], item: string) {
  const i = list.indexOf(item)
  if (i >= 0) list.splice(i, 1)
  else list.push(item)
}

onMounted(async () => {
  const p = await fetchProfile()
  if (!p) return
  major.value = p.major || '计算机科学'
  interests.value = p.interests ?? []
  strengths.value = p.strengths ?? []
})

async function plant() {
  await updateProfile({ major: major.value, interests: interests.value, strengths: strengths.value })
  router.push('/time-preference')
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <h2>告诉我你的土壤条件 🌱</h2>
    </header>

    <p class="progress">成长进度 2/4</p>
    <p class="page-sub">福小禾会根据你的主修、兴趣和能力，为你推荐最适合复合生长的方向。</p>

    <section class="card">
      <h4 class="card-title">🌾 主修专业 (单选)</h4>
      <div class="chips">
        <button v-for="m in majors" :key="m" class="chip" :class="{ selected: major === m }" @click="major = m">{{ m }}</button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">✨ 兴趣方向 (可多选)</h4>
      <div class="chips">
        <button v-for="o in interestOptions" :key="o" class="chip" :class="{ selected: interests.includes(o) }" @click="toggle(interests, o)">{{ o }}</button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">💪 能力特长 (可多选)</h4>
      <div class="chips">
        <button v-for="o in strengthOptions" :key="o" class="chip" :class="{ selected: strengths.includes(o) }" @click="toggle(strengths, o)">{{ o }}</button>
      </div>
    </section>

    <button class="btn-primary" @click="plant">播下种子，开始生长</button>
  </div>
</template>

<style scoped>
.progress { font-size: var(--text-sm); color: var(--brand-strong); font-weight: var(--weight-semibold); }
.page-sub { font-size: var(--text-sm); color: var(--text-muted); line-height: 1.6; margin-bottom: var(--space-2); }
.card-title { font-size: var(--text-base); font-weight: var(--weight-semibold); color: var(--text-primary); margin-bottom: var(--space-3); }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
</style>
