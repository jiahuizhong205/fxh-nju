<script setup lang="ts">
import { ref, onMounted } from 'vue'

const profile = ref<any>(null)
const msg = ref('')

// form state
const major = ref('')
const grade = ref('大一')
const campus = ref('仙林校区')
const careerGoals = ref('')
const mathWillingness = ref(false)
const campusFlexibility = ref(false)
const creditBudget = ref(50)
const certificateGoal = ref('')

const grades = ['大一', '大二', '大三', '大四']
const campuses = ['仙林校区', '鼓楼校区', '苏州校区']
const certGoals = [
  { value: 'degree', label: '辅修学士学位' },
  { value: 'cert', label: '辅修结业证明' },
  { value: 'none', label: '暂无证书目标' },
]

onMounted(async () => {
  const res = await fetch('/api/v1/profile')
  const data = await res.json()
  if (data.profile) {
    profile.value = data.profile
    major.value = data.profile.major
    grade.value = data.profile.grade
    campus.value = data.profile.campus || ''
    careerGoals.value = data.profile.career_goals
    mathWillingness.value = data.profile.math_willingness
    campusFlexibility.value = data.profile.campus_flexibility
    creditBudget.value = data.profile.credit_budget || 50
    certificateGoal.value = data.profile.certificate_goal
  }
})

async function save() {
  const params = new URLSearchParams()
  params.set('major', major.value)
  params.set('grade', grade.value)
  params.set('campus', campus.value)
  params.set('career_goals', careerGoals.value)
  params.set('math_willingness', String(mathWillingness.value))
  params.set('campus_flexibility', String(campusFlexibility.value))
  params.set('credit_budget', String(creditBudget.value))
  params.set('certificate_goal', certificateGoal.value)

  const res = await fetch('/api/v1/profile?' + params, { method: 'PUT' })
  const data = await res.json()
  profile.value = data.profile
  msg.value = '画像已保存！'
  setTimeout(() => msg.value = '', 3000)
}
</script>

<template>
  <div class="profile-page">
    <div class="profile-card">
      <h2>学生画像</h2>
      <p class="desc">填写基本信息，福小禾将为你精准推荐辅修方向。</p>

      <div class="form-grid">
        <div class="field">
          <label>主修专业 <span class="req">*</span></label>
          <input v-model="major" placeholder="如：汉语言文学、计算机科学与技术" />
        </div>
        <div class="field">
          <label>所在年级 <span class="req">*</span></label>
          <select v-model="grade">
            <option v-for="g in grades" :key="g" :value="g">{{ g }}</option>
          </select>
        </div>
        <div class="field">
          <label>就读校区</label>
          <select v-model="campus">
            <option v-for="c in campuses" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field">
          <label>证书目标</label>
          <select v-model="certificateGoal">
            <option value="">请选择</option>
            <option v-for="cg in certGoals" :key="cg.value" :value="cg.value">{{ cg.label }}</option>
          </select>
        </div>
        <div class="field">
          <label>可接受学分上限</label>
          <input v-model.number="creditBudget" type="number" min="0" max="120" />
        </div>
        <div class="field full">
          <label>职业目标</label>
          <input v-model="careerGoals" placeholder="如：希望从事金融或传媒行业" />
        </div>
        <div class="field checkbox-group">
          <label>
            <input type="checkbox" v-model="mathWillingness" />
            愿意修读高等数学
          </label>
          <span class="hint">（理科辅修通常要求高数，不修最高只能拿结业证明）</span>
        </div>
        <div class="field checkbox-group">
          <label>
            <input type="checkbox" v-model="campusFlexibility" />
            接受跨校区通勤
          </label>
          <span class="hint">（鼓楼-仙林约40-60分钟公交）</span>
        </div>
      </div>

      <button class="btn-save" @click="save" :disabled="!major || !grade">
        保存画像
      </button>
      <p v-if="msg" class="toast">{{ msg }}</p>

      <div v-if="profile" class="current-profile">
        <h4>当前画像</h4>
        <ul>
          <li>专业：{{ profile.major }}</li>
          <li>年级：{{ profile.grade }} · {{ profile.campus || '未填' }}</li>
          <li>证书目标：{{ profile.certificate_goal || '未填' }}</li>
          <li>数学：{{ profile.math_willingness ? '接受' : '不接受' }}</li>
          <li>跨校区：{{ profile.campus_flexibility ? '接受' : '不接受' }}</li>
          <li>学分预算：{{ profile.credit_budget || '不限' }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-page {
  flex: 1; display: flex; justify-content: center; padding: 32px 20px;
  overflow-y: auto;
}
.profile-card {
  width: 100%; max-width: 560px; background: #fff;
  border-radius: 12px; padding: 28px; box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
h2 { font-size: 1.3rem; margin-bottom: 4px; }
.desc { color: #6b7280; font-size: 0.9rem; margin-bottom: 20px; }

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.field.full { grid-column: span 2; }
.field.checkbox-group { grid-column: span 2; }

.field label { font-size: 0.85rem; font-weight: 500; display: block; margin-bottom: 4px; color: #374151; }
.req { color: #ef4444; }
.field input, .field select {
  width: 100%; padding: 8px 12px; border: 1px solid #d4d4d8; border-radius: 8px;
  font-size: 0.9rem; font-family: inherit;
}
.field input:focus, .field select:focus { border-color: #7c3aed; outline: none; }

.checkbox-group label { font-size: 0.9rem; cursor: pointer; display: flex; align-items: center; gap: 6px; }
.checkbox-group input[type="checkbox"] { width: auto; }
.hint { font-size: 0.78rem; color: #9ca3af; display: block; margin-top: 2px; margin-left: 22px; }

.btn-save {
  margin-top: 20px; width: 100%; padding: 10px; background: #7c3aed;
  color: #fff; border: none; border-radius: 8px; font-size: 1rem;
  cursor: pointer; font-weight: 500;
}
.btn-save:disabled { background: #c4b5fd; cursor: not-allowed; }

.toast { margin-top: 10px; text-align: center; color: #16a34a; font-size: 0.9rem; }

.current-profile {
  margin-top: 24px; padding-top: 20px; border-top: 1px solid #e5e7eb;
}
.current-profile h4 { font-size: 0.95rem; margin-bottom: 8px; color: #6b7280; }
.current-profile ul { list-style: none; font-size: 0.88rem; color: #374151; }
.current-profile li { padding: 3px 0; }
</style>
