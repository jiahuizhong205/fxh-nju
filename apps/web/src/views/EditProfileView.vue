<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchProfile, fetchPrograms, updateProfile, updateNickname } from '../api/client'
import { useAuthStore } from '../stores/auth'
import BackButton from '../components/BackButton.vue'

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
const majors = ref<string[]>([])
const avatarSrc = ref('/illustrations/avatar-wreath.png')
const avatarInput = ref<HTMLInputElement | null>(null)

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
  const [p, programs] = await Promise.all([fetchProfile(), fetchPrograms()])
  majors.value = programs.map(program => program.name)
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

function chooseAvatar() {
  avatarInput.value?.click()
}

function handleAvatarChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (file) avatarSrc.value = URL.createObjectURL(file)
}

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
  await updateProfile({
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
  <div class="page edit-profile-page">
    <header class="page-head">
      <BackButton fallback="/profile" />
      <div>
        <h2>编辑个人资料 🍃</h2>
        <p>我的园丁卡片 🌿</p>
      </div>
    </header>

    <section class="avatar-section">
      <button type="button" class="avatar-button" aria-label="更换园丁头像" @click="chooseAvatar">
        <img class="avatar" :src="avatarSrc" alt="头像" />
        <span class="avatar-camera" aria-hidden="true">▣</span>
      </button>
      <input ref="avatarInput" class="avatar-input" type="file" accept="image/*" @change="handleAvatarChange" />
      <button type="button" class="avatar-hint" @click="chooseAvatar">点击更换园丁头像</button>
    </section>

    <section class="profile-fields">
      <div class="form-field">
        <label>昵称</label>
        <input v-model="nickname" placeholder="给自己起个好听的称呼" maxlength="50" />
      </div>
      <div class="form-field">
        <label>主修专业</label>
        <select v-model="major" :disabled="!majors.length">
          <option disabled value="">请选择你的主修专业</option>
          <option v-for="m in majors" :key="m" :value="m">{{ m }}</option>
        </select>
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

    <section class="profile-group interest-group">
      <h4 class="group-title">你选择的辅修专业阳光☀️</h4>
      <div class="chips">
        <button v-for="m in interestOptions" :key="m" class="chip" :class="{ selected: interests.includes(m) }" @click="toggle(interests, m)">{{ m }}</button>
      </div>
    </section>

    <section class="profile-group strength-group">
      <h4 class="group-title">你最擅长的园艺技能 🌱</h4>
      <div class="chips">
        <button v-for="s in strengthOptions" :key="s" class="chip" :class="{ selected: strengths.includes(s) }" @click="toggle(strengths, s)">{{ s }}</button>
      </div>
    </section>

    <details class="advanced-section">
      <summary>更多画像信息</summary>
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
    </details>

    <button class="btn-primary" @click="save">保存园丁卡片</button>
    <p class="foot">你的信息仅用于福小禾提供个性化推荐，不会对外展示 🍀</p>
  </div>
</template>

<style scoped>
.edit-profile-page { position: relative; gap: var(--space-5); padding-top: var(--space-5); }
.page-head h2 { color: var(--text-primary); font-size: var(--text-2xl); }
.page-head p { margin-top: var(--space-1); color: var(--brand-strong); font-size: var(--text-sm); }
.avatar-section { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); }
.avatar-button { position: relative; width: 108px; height: 108px; padding: 5px; border: 2px dashed var(--brand); border-radius: var(--radius-full); background: transparent; cursor: pointer; }
.avatar { width: 100%; height: 100%; border-radius: var(--radius-full); object-fit: cover; display: block; }
.avatar-camera { position: absolute; right: -4px; bottom: -1px; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; border: 3px solid var(--bg-page); border-radius: var(--radius-full); background: var(--brand-strong); color: #fff; font-size: var(--text-sm); }
.avatar-input { display: none; }
.avatar-hint { border: none; background: transparent; color: var(--brand-strong); font: inherit; font-size: var(--text-sm); font-weight: var(--weight-semibold); cursor: pointer; }
.profile-fields { display: flex; flex-direction: column; gap: var(--space-1); }
.profile-fields .form-field { margin-bottom: var(--space-3); }
.profile-fields .form-field:last-child { margin-bottom: 0; }
.profile-fields .form-field input, .profile-fields .form-field select { min-height: 52px; border: 1px solid var(--bg-green-soft); border-radius: var(--radius-full); background: var(--bg-surface); font-size: var(--text-md); }
.profile-fields .form-field select { appearance: auto; }
.chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.profile-group { padding-top: var(--space-1); }
.group-title { margin-bottom: var(--space-3); font-size: var(--text-base); font-weight: var(--weight-semibold); }
.interest-group .group-title { color: var(--accent-purple); }
.strength-group .group-title { color: var(--brand-strong); }
.profile-group .chip { padding: var(--space-2) var(--space-3); }
.interest-group .chip.selected { background: var(--accent-purple-soft); border-color: var(--accent-purple); color: var(--accent-purple); }
.strength-group .chip.selected { background: var(--bg-green-soft); border-color: var(--brand); color: var(--brand-strong); }
.advanced-section { padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); }
.advanced-section summary { color: var(--text-secondary); font-size: var(--text-sm); font-weight: var(--weight-semibold); cursor: pointer; }
.advanced-section[open] summary { margin-bottom: var(--space-4); color: var(--brand-strong); }
.switch-row { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0; }
.switch-label { font-size: var(--text-sm); color: var(--text-secondary); }
.foot { text-align: center; font-size: var(--text-xs); color: var(--text-muted); margin-top: var(--space-2); }
</style>
