<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, saveProfile, updateNickname } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const nickname = ref('')
const major = ref('')
const grade = ref('大二')
const campus = ref('仙林校区')
const interests = ref<string[]>([])
const strengths = ref<string[]>([])
const careerGoals = ref('')
const mathWillingness = ref(false)
const campusFlexibility = ref(false)
const creditBudget = ref(0)
const certificateGoal = ref('none')

const grades = ['大一', '大二', '大三', '大四']
const campuses = ['仙林校区', '鼓楼校区', '苏州校区']
const interestOptions = ['写作', '传播', '数据分析', '编程', '设计', '法律', '金融', '人工智能']
const strengthOptions = ['创意思维', '逻辑推理', '数据处理', '表达沟通', '动手实验', '组织协调', '编程基础', '外语能力']
const certificateOptions = [
  { value: 'degree', label: '辅修学位' },
  { value: 'cert', label: '结业证书' },
  { value: 'none', label: '仅旁听 / 不考证' },
]

onMounted(async () => {
  nickname.value = auth.user?.nickname || ''
  const p = await fetchProfile()
  if (!p) return
  major.value = p.major
  grade.value = p.grade
  campus.value = p.campus || '仙林校区'
  interests.value = p.interests ?? []
  strengths.value = p.strengths ?? []
  careerGoals.value = p.career_goals
  mathWillingness.value = p.math_willingness
  campusFlexibility.value = p.campus_flexibility
  creditBudget.value = p.credit_budget
  certificateGoal.value = p.certificate_goal || 'none'
})

function toggle(list: string[], label: string) {
  const i = list.indexOf(label)
  if (i >= 0) list.splice(i, 1)
  else list.push(label)
}

async function save() {
  if (!nickname.value.trim()) {
    alert('请填写昵称')
    return
  }
  if (!major.value.trim()) {
    alert('请填写主修专业')
    return
  }
  try {
    await updateNickname(nickname.value.trim())
    auth.setNickname(nickname.value.trim())
  } catch (e: any) {
    alert(e.message)
    return
  }
  await saveProfile({
    major: major.value,
    grade: grade.value,
    campus: campus.value,
    interests: interests.value,
    strengths: strengths.value,
    career_goals: careerGoals.value,
    math_willingness: mathWillingness.value,
    campus_flexibility: campusFlexibility.value,
    credit_budget: creditBudget.value,
    certificate_goal: certificateGoal.value,
  })
  router.push('/profile')
}
</script>

<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/profile" class="back">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m15 18-6-6 6-6"/>
        </svg>
      </router-link>
      <h2>编辑个人资料</h2>
    </header>

    <p class="page-sub">我的园丁卡片 🌿</p>

    <section class="card avatar-row">
      <img class="avatar" src="/illustrations/avatar-wreath.png" alt="头像" />
      <button class="btn-avatar">点击更换园丁头像</button>
    </section>

    <section class="card">
      <div class="form-field">
        <label>昵称</label>
        <input v-model="nickname" placeholder="给自己起个好听的称呼" maxlength="50" />
      </div>
      <div class="form-field">
        <label>主修专业</label>
        <input v-model="major" placeholder="请输入主修专业" />
      </div>
      <div class="form-field">
        <label>年级</label>
        <select v-model="grade">
          <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
        </select>
      </div>
      <div class="form-field">
        <label>所在校区</label>
        <select v-model="campus">
          <option v-for="c in campuses" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">兴趣方向 ☀️</h4>
      <div class="chips">
        <button v-for="m in interestOptions" :key="m" class="chip" :class="{ selected: interests.includes(m) }" @click="toggle(interests, m)">{{ m }}</button>
      </div>
    </section>

    <section class="card">
      <h4 class="card-title">擅长技能 🌱</h4>
      <div class="chips">
        <button v-for="s in strengthOptions" :key="s" class="chip" :class="{ selected: strengths.includes(s) }" @click="toggle(strengths, s)">{{ s }}</button>
      </div>
    </section>

    <section class="card">
      <div class="form-field">
        <label>职业目标</label>
        <input v-model="careerGoals" placeholder="例如：想进入互联网内容生态 / 科技传播领域" />
      </div>
      <div class="switch-row">
        <span class="switch-label">愿意修读高等数学</span>
        <div class="toggle" :class="{ on: mathWillingness }" @click="mathWillingness = !mathWillingness"><div class="knob"></div></div>
      </div>
      <div class="switch-row">
        <span class="switch-label">接受跨校区通勤</span>
        <div class="toggle" :class="{ on: campusFlexibility }" @click="campusFlexibility = !campusFlexibility"><div class="knob"></div></div>
      </div>
      <div class="form-field">
        <label>可投入学分预算</label>
        <input v-model.number="creditBudget" type="number" min="0" placeholder="例如 45" />
      </div>
      <div class="form-field">
        <label>证书目标</label>
        <select v-model="certificateGoal">
          <option v-for="o in certificateOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
      </div>
    </section>

    <button class="btn-primary" @click="save">保存园丁卡片</button>
    <p class="foot">你的信息仅用于福小禾提供个性化推荐，不会对外展示 🍀</p>
  </div>
</template>

<style scoped>
.avatar-row { display: flex; align-items: center; gap: var(--space-4); }
.avatar { width: 92px; height: 92px; border-radius: var(--radius-full); object-fit: cover; flex-shrink: 0; }
.btn-avatar { padding: var(--space-2) var(--space-3); border: 1px solid var(--border); background: #fff; border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary); cursor: pointer; font-family: inherit; }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.switch-row { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0; }
.switch-label { font-size: var(--text-sm); color: var(--text-secondary); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); margin-top: var(--space-2); }
</style>
