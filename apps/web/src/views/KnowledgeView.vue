<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { authHeaders, searchKnowledge, type SearchResult } from '../api/client'
import BackButton from '../components/BackButton.vue'

interface Document {
  id: string; title: string; trust_level: string; source_type: string
  knowledge_version: string; is_active: boolean
  valid_from: string | null; created_at: string
}

const docs = ref<Document[]>([])
const loading = ref(false)
const filterActive = ref<boolean | null>(null)
const filterLevel = ref('')

// upload form
const uploadTitle = ref('')
const uploadContent = ref('')
const uploadLevel = ref('A')
const uploadType = ref('policy')
const uploadMode = ref<'text' | 'file'>('text')
const uploadFile = ref<File | null>(null)
const uploadMsg = ref('')
const uploadError = ref('')

// version
const versionInput = ref('')

async function loadDocs() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (filterActive.value !== null) params.set('is_active', String(filterActive.value))
    if (filterLevel.value) params.set('trust_level', filterLevel.value)
    const res = await fetch(`/api/v1/knowledge/documents?${params}`, { headers: authHeaders() })
    const data = await res.json().catch(() => [])
    if (!res.ok) throw new Error(data.detail || '文档列表加载失败')
    docs.value = data
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : '文档列表加载失败'
  } finally {
    loading.value = false
  }
}

function onFileSelected(event: Event) {
  uploadFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

async function handleUpload() {
  uploadMsg.value = ''
  uploadError.value = ''
  if (!uploadTitle.value.trim()) {
    uploadError.value = '请填写文档标题'
    return
  }
  if (uploadMode.value === 'text' && !uploadContent.value.trim()) {
    uploadError.value = '请填写文档内容'
    return
  }
  if (uploadMode.value === 'file' && !uploadFile.value) {
    uploadError.value = '请选择要上传的文件'
    return
  }
  const form = new FormData()
  form.append('title', uploadTitle.value)
  form.append('trust_level', uploadLevel.value)
  form.append('source_type', uploadType.value)

  const ep = uploadMode.value === 'text' ? '/api/v1/knowledge/documents/text' : '/api/v1/knowledge/documents'
  if (uploadMode.value === 'file') {
    form.append('file', uploadFile.value as File)
  } else {
    form.append('content', uploadContent.value)
  }

  try {
    const res = await fetch(ep, { method: 'POST', headers: authHeaders(), body: form })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '上传失败')
    if (data.error) throw new Error(data.error)
    uploadMsg.value = `上传成功: ${data.title}`
    uploadTitle.value = ''
    uploadContent.value = ''
    uploadFile.value = null
    await loadDocs()
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : '上传失败，请稍后重试'
  }
}

async function activateVersion() {
  if (!versionInput.value.trim()) return
  try {
    const res = await fetch(`/api/v1/knowledge/versions/${versionInput.value}/activate`, { method: 'POST', headers: authHeaders() })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || '版本激活失败')
    uploadMsg.value = `已激活版本 ${data.activated_version}，${data.document_count} 篇文档`
    await loadDocs()
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : '版本激活失败'
  }
}

async function deactivateDoc(id: string) {
  try {
    const res = await fetch(`/api/v1/knowledge/documents/${id}`, { method: 'DELETE', headers: authHeaders() })
    if (!res.ok) throw new Error('文档停用失败')
    await loadDocs()
  } catch (e) {
    uploadError.value = e instanceof Error ? e.message : '文档停用失败'
  }
}

function toggleFilter(val: boolean | null) {
  filterActive.value = val
  loadDocs()
}

// search
const searchQuery = ref('')
const searchResults = ref<SearchResult[]>([])
const searchMsg = ref('')
const searching = ref(false)

async function handleSearch() {
  const q = searchQuery.value.trim()
  if (!q) return
  searching.value = true
  searchMsg.value = ''
  try {
    const data = await searchKnowledge(q)
    searchResults.value = data.results
    searchMsg.value = `检索到 ${data.results.length} 条结果`
  } catch (e: any) {
    searchResults.value = []
    searchMsg.value = `检索失败: ${e.message}`
  } finally {
    searching.value = false
  }
}

onMounted(loadDocs)
</script>

<template>
  <div class="knowledge-page">
    <div class="kb-sidebar">
      <h3>知识库管理</h3>
      <div class="filter-group">
        <label>状态</label>
        <div class="filter-btns">
          <button :class="{ active: filterActive === null }" @click="toggleFilter(null)">全部</button>
          <button :class="{ active: filterActive === true }" @click="toggleFilter(true)">活跃</button>
          <button :class="{ active: filterActive === false }" @click="toggleFilter(false)">停用</button>
        </div>
      </div>
      <div class="filter-group">
        <label>信任等级</label>
        <select v-model="filterLevel" @change="loadDocs">
          <option value="">全部</option>
          <option value="S">S 级</option>
          <option value="A">A 级</option>
          <option value="B">B 级</option>
          <option value="C">C 级</option>
        </select>
      </div>

      <div class="version-section">
        <h4>版本切换</h4>
        <input v-model="versionInput" placeholder="输入版本号 (v1/v2)" />
        <button @click="activateVersion">激活版本</button>
        <p v-if="uploadMsg" class="msg">{{ uploadMsg }}</p>
        <p v-if="uploadError" class="error">{{ uploadError }}</p>
      </div>
    </div>

    <div class="kb-main">
      <div class="kb-title">
        <BackButton fallback="/" />
        <h2>知识森林</h2>
      </div>
      <!-- 检索 -->
      <h3>知识检索</h3>
      <div class="search-box">
        <input v-model="searchQuery" placeholder="输入问题，检索知识库（如：辅修学分要求）" @keyup.enter="handleSearch" />
        <button @click="handleSearch" :disabled="searching">{{ searching ? '检索中...' : '检索' }}</button>
      </div>
      <p v-if="searchMsg" class="msg">{{ searchMsg }}</p>
      <div v-if="searchResults.length" class="search-results">
        <div v-for="r in searchResults" :key="r.chunk_id" class="result-item">
          <div class="result-head">
            <span class="result-title">{{ r.document_title }}</span>
            <span class="badge" :class="'t' + r.trust_level">{{ r.trust_level }}</span>
            <span class="result-score">score {{ r.score.toFixed(2) }}</span>
          </div>
          <p class="result-excerpt">{{ r.content.slice(0, 200) }}{{ r.content.length > 200 ? '...' : '' }}</p>
        </div>
      </div>

      <!-- 文档列表 -->
      <h3 style="margin-top: 24px">文档列表 ({{ docs.length }})</h3>
      <div v-if="loading" class="loading">加载中...</div>
      <table v-else>
        <thead>
          <tr><th>标题</th><th>等级</th><th>版本</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="d in docs" :key="d.id" :class="{ inactive: !d.is_active }">
            <td class="title">{{ d.title }}</td>
            <td><span class="badge" :class="'t' + d.trust_level">{{ d.trust_level }}</span></td>
            <td>{{ d.knowledge_version }}</td>
            <td><span :class="d.is_active ? 'active-tag' : 'off-tag'">{{ d.is_active ? '活跃' : '停用' }}</span></td>
            <td>
              <button v-if="d.is_active" class="btn-sm btn-danger" @click="deactivateDoc(d.id)">停用</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 上传 -->
      <h3 style="margin-top: 24px">上传文档</h3>
      <div class="upload-form">
        <input v-model="uploadTitle" placeholder="文档标题" />
        <div class="upload-mode">
          <button :class="{ active: uploadMode === 'text' }" @click="uploadMode = 'text'">文本</button>
          <button :class="{ active: uploadMode === 'file' }" @click="uploadMode = 'file'">文件 / PDF</button>
        </div>
        <textarea v-if="uploadMode === 'text'" v-model="uploadContent" placeholder="文档内容（纯文本）" rows="6" />
        <label v-else class="file-picker">选择文本或 PDF 文件<input type="file" accept=".txt,.md,.pdf,text/plain,text/markdown,application/pdf" @change="onFileSelected" /></label>
        <p v-if="uploadFile" class="msg">已选择：{{ uploadFile.name }}</p>
        <div class="upload-row">
          <select v-model="uploadLevel">
            <option value="S">S 级</option>
            <option value="A">A 级</option>
            <option value="B">B 级</option>
            <option value="C">C 级</option>
          </select>
          <select v-model="uploadType">
            <option value="policy">政策</option>
            <option value="regulation">法规</option>
            <option value="course_catalog">培养方案</option>
            <option value="job_posting">招聘信息</option>
            <option value="other">其他</option>
          </select>
          <button @click="handleUpload">上传</button>
        </div>
        <p v-if="uploadMsg" class="msg">{{ uploadMsg }}</p>
        <p v-if="uploadError" class="error">{{ uploadError }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.knowledge-page { display: flex; flex: 1; overflow: hidden; }
.kb-sidebar {
  width: 220px; background: #fff; border-right: 1px solid #e5e7eb;
  padding: 16px; display: flex; flex-direction: column; gap: 16px; overflow-y: auto;
}
.kb-sidebar h3 { font-size: 1rem; margin-bottom: 4px; }
.kb-sidebar h4 { font-size: 0.9rem; margin-bottom: 4px; }

.filter-group label { font-size: 0.8rem; color: #6b7280; display: block; margin-bottom: 4px; }
.filter-btns { display: flex; gap: 4px; }
.filter-btns button {
  flex: 1; padding: 4px 8px; font-size: 0.78rem; border: 1px solid #d4d4d8;
  background: #fff; border-radius: 4px; cursor: pointer;
}
.filter-btns button.active { background: var(--bg-green-soft); color: var(--brand-strong); border-color: var(--brand); }
select { padding: 6px 8px; border: 1px solid #d4d4d8; border-radius: 6px; font-size: 0.85rem; width: 100%; }

.version-section { border-top: 1px solid #e5e7eb; padding-top: 12px; }
.version-section input {
  width: 100%; padding: 6px 8px; border: 1px solid #d4d4d8; border-radius: 6px;
  font-size: 0.85rem; margin-bottom: 6px;
}
.version-section button {
  width: 100%; padding: 6px; background: #5a7a6b; color: #fff; border: none;
  border-radius: 6px; cursor: pointer; font-size: 0.85rem;
}

.kb-main { flex: 1; padding: 20px; overflow-y: auto; }
.kb-title { display: flex; align-items: center; gap: var(--space-3); margin-bottom: 20px; }
.kb-title h2 { font-size: var(--text-xl); color: var(--text-primary); }
.kb-main h3 { margin-bottom: 12px; }

table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #f3f4f6; }
th { color: #6b7280; font-weight: 500; font-size: 0.8rem; }
.title { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.inactive { opacity: 0.5; }

.badge { padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; }
.tS { background: #dcfce7; color: #166534; }
.tA { background: #dbeafe; color: #1e40af; }
.tB { background: #fef3c7; color: #92400e; }
.tC { background: #fee2e2; color: #991b1b; }
.active-tag { color: #16a34a; font-size: 0.8rem; }
.off-tag { color: #dc2626; font-size: 0.8rem; }

.btn-sm {
  padding: 2px 10px; font-size: 0.78rem; border-radius: 4px; cursor: pointer; border: none;
}
.btn-danger { background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; }

.upload-form { display: flex; flex-direction: column; gap: 10px; max-width: 600px; }
.upload-form input, .upload-form textarea {
  padding: 8px 12px; border: 1px solid #d4d4d8; border-radius: 8px; font-size: 0.9rem;
  font-family: inherit;
}
.upload-row { display: flex; gap: 8px; align-items: center; }
.upload-row select { width: auto; flex: 1; }
.upload-row button {
  padding: 8px 20px; background: #5a7a6b; color: #fff; border: none;
  border-radius: 8px; cursor: pointer;
}
.msg { font-size: 0.85rem; color: #6b7280; }
.error { font-size: 0.85rem; color: #b91c1c; }
.loading { padding: 20px; color: #9ca3af; }

.upload-mode { display: flex; gap: 6px; }
.upload-mode button { padding: 6px 14px; border: 1px solid #d4d4d8; background: #fff; border-radius: 6px; cursor: pointer; }
.upload-mode button.active { background: var(--bg-green-soft); border-color: var(--brand); color: var(--brand-strong); }
.file-picker { padding: 18px; border: 1px dashed #a1a1aa; border-radius: 8px; color: #6b7280; cursor: pointer; }
.file-picker input { display: block; margin-top: 8px; }

.search-box { display: flex; gap: 8px; margin-bottom: 8px; max-width: 600px; }
.search-box input {
  flex: 1; padding: 8px 12px; border: 1px solid #d4d4d8; border-radius: 8px; font-size: 0.9rem;
}
.search-box button {
  padding: 8px 20px; background: #5a7a6b; color: #fff; border: none; border-radius: 8px; cursor: pointer;
}
.search-box button:disabled { opacity: 0.6; cursor: not-allowed; }
.search-results { margin-top: 12px; display: flex; flex-direction: column; gap: 10px; max-width: 700px; }
.result-item { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; }
.result-head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.result-title { font-weight: 600; font-size: 0.9rem; }
.result-score { font-size: 0.75rem; color: #6b7280; }
.result-excerpt { font-size: 0.85rem; color: #374151; margin: 0; line-height: 1.5; }
</style>
