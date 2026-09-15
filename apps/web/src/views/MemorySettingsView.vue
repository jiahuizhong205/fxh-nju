<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { createMemory, deleteMemory, fetchMemories, fetchMemoryPreferences, MemoryApiError, saveMemoryPreferences, updateMemory, type MemoryCategory, type UserMemory } from '../api/client'
import BackButton from '../components/BackButton.vue'
import { appendMemoryPage, appendRequestCursor, closeMemoryDialog, createLatestRequestGuard, createMemoryListCoordinator, initialMemoryPreferenceState, memoryPreferenceLoaded, memoryPreferenceReadFailed, nextAppendError, restoreDialogTrigger, runConfirmedMemoryDelete, showMemoryDialog, syncMemoryAfterSave, trapDialogTabFocus } from './memorySettingsState'

const categories: Array<{ value?: MemoryCategory; label: string }> = [
  { label: '全部' }, { value: 'learning_goal', label: '学习目标' }, { value: 'program_preference', label: '专业偏好' },
  { value: 'interest_strength', label: '兴趣优势' }, { value: 'study_constraint', label: '学习限制' }, { value: 'career_goal', label: '职业目标' }, { value: 'confirmed_plan', label: '已确认计划' },
]
const memories = ref<UserMemory[]>([])
const selectedCategory = ref<MemoryCategory | undefined>()
const nextCursor = ref<string | null>(null)
const initialLoading = ref(true)
const loadingMore = ref(false)
const initialListError = ref('')
const appendError = ref('')
const preference = ref(initialMemoryPreferenceState())
const preferencesSaving = ref(false)
const preferenceError = ref('')
const preferenceSaveFailed = ref(false)
const formOpen = ref(false)
const editingId = ref<string | null>(null)
const formSaving = ref(false)
const formError = ref('')
const deletingId = ref<string | null>(null)
const deleteErrorId = ref<string | null>(null)
const actionError = ref('')
const status = ref('')
const formDialog = ref<HTMLDialogElement | null>(null)
const categoryField = ref<HTMLSelectElement | null>(null)
const addButton = ref<HTMLButtonElement | null>(null)
const formTrigger = ref<HTMLElement | null>(null)
const listCoordinator = createMemoryListCoordinator()
const preferenceRequests = createLatestRequestGuard()
const preferenceValue = computed(() => preference.value.value)
const canTogglePreference = computed(() => preferenceValue.value !== null && !preference.value.loading && !preferencesSaving.value)
const canAddMemory = computed(() => listCoordinator.canAdd(initialLoading.value, initialListError.value))
const form = reactive({ category: 'learning_goal' as MemoryCategory, content: '', importance: .5 })

const safeMessage = (action: string) => `${action}暂时未完成，请稍后重试。`
const categoryLabel = (category: MemoryCategory) => categories.find(item => item.value === category)?.label ?? '未分类'

async function loadMemories(append = false) {
  if (append && (!nextCursor.value || loadingMore.value)) return
  const request = listCoordinator.begin()
  if (append) { appendError.value = ''; loadingMore.value = true } else { initialListError.value = ''; appendError.value = nextAppendError(false, appendError.value); initialLoading.value = true }
  try {
    const page = await fetchMemories(selectedCategory.value, append ? appendRequestCursor(nextCursor.value) : undefined)
    if (!listCoordinator.isCurrent(request)) return
    const nextPage = append ? appendMemoryPage(memories.value, page) : { rows: page.items, nextCursor: page.next_cursor }
    memories.value = nextPage.rows
    nextCursor.value = nextPage.nextCursor
  } catch {
    if (listCoordinator.isCurrent(request)) append ? appendError.value = safeMessage('加载更多记忆') : initialListError.value = safeMessage('记忆列表加载')
  } finally {
    if (listCoordinator.isCurrent(request)) append ? loadingMore.value = false : initialLoading.value = false
  }
}

async function loadPreferences() {
  const request = preferenceRequests.begin()
  preference.value = initialMemoryPreferenceState()
  preferenceError.value = ''; preferenceSaveFailed.value = false
  try {
    const result = await fetchMemoryPreferences()
    if (preferenceRequests.isCurrent(request)) preference.value = memoryPreferenceLoaded(preference.value, result.auto_capture_enabled)
  } catch {
    if (preferenceRequests.isCurrent(request)) { preference.value = memoryPreferenceReadFailed(); preferenceError.value = safeMessage('自动记忆设置加载') }
  }
}

async function toggleAutoCapture() {
  if (!canTogglePreference.value || preferenceValue.value === null) return
  const savedValue = preferenceValue.value
  preferencesSaving.value = true; preferenceError.value = ''; preferenceSaveFailed.value = false
  try {
    const result = await saveMemoryPreferences({ auto_capture_enabled: !savedValue })
    preference.value = memoryPreferenceLoaded(preference.value, result.auto_capture_enabled)
    status.value = result.auto_capture_enabled ? '已开启自动记忆。' : '已关闭自动记忆。'
  } catch {
    preference.value = memoryPreferenceLoaded(preference.value, savedValue)
    preferenceError.value = safeMessage('自动记忆设置保存'); preferenceSaveFailed.value = true
  } finally { preferencesSaving.value = false }
}
function retryPreferences() { if (preferenceSaveFailed.value) void toggleAutoCapture(); else void loadPreferences() }
function selectCategory(category?: MemoryCategory) { if (selectedCategory.value !== category || initialListError.value) { selectedCategory.value = category; void loadMemories() } }
function captureTrigger(event?: Event) { formTrigger.value = event?.currentTarget instanceof HTMLElement ? event.currentTarget : document.activeElement instanceof HTMLElement ? document.activeElement : null }
function focusForm() { if (categoryField.value) categoryField.value.focus(); else formDialog.value?.focus() }
async function restoreFormFocus() { await nextTick(); restoreDialogTrigger(formTrigger.value, addButton.value); formTrigger.value = null }
async function showFormDialog() { await nextTick(); if (formDialog.value) showMemoryDialog(formDialog.value, focusForm) }
function openCreateForm(event?: Event) { if (!canAddMemory.value) return; captureTrigger(event); editingId.value = null; form.category = selectedCategory.value ?? 'learning_goal'; form.content = ''; form.importance = .5; formError.value = ''; formOpen.value = true; void showFormDialog() }
function openEditForm(memory: UserMemory, event?: Event) { captureTrigger(event); editingId.value = memory.id; form.category = memory.category; form.content = memory.content; form.importance = memory.importance; formError.value = ''; formOpen.value = true; void showFormDialog() }
function closeForm() { if (!formSaving.value && formDialog.value) { formError.value = ''; closeMemoryDialog(formDialog.value, () => undefined) } }
function onDialogCancel(event: Event) { event.preventDefault(); closeForm() }
function onDialogClosed() { formOpen.value = false; void restoreFormFocus() }
function onDialogKeydown(event: KeyboardEvent) {
  const dialog = formDialog.value
  if (!dialog) return
  const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not([disabled]), select:not([disabled]), textarea:not([disabled]), input:not([disabled])'))
  trapDialogTabFocus(event, focusable, document.activeElement)
}

async function submitForm() {
  if (formSaving.value) return
  const content = form.content.trim()
  if (!content) { formError.value = '请输入要保存的记忆内容。'; return }
  formSaving.value = true; formError.value = ''; let saved = false
  try {
    const savedMemory = editingId.value
      ? await updateMemory(editingId.value, { category: form.category, content, importance: form.importance })
      : await createMemory({ category: form.category, content, importance: form.importance })
    listCoordinator.invalidateForSave()
    memories.value = syncMemoryAfterSave(memories.value, savedMemory, selectedCategory.value)
    const stableList = listCoordinator.stableAfterSave()
    initialLoading.value = stableList.initialLoading
    initialListError.value = stableList.initialListError
    appendError.value = stableList.appendError
    loadingMore.value = stableList.loadingMore
    status.value = editingId.value ? '记忆已更新。' : '记忆已添加。'
    saved = true
  } catch (error) {
    formError.value = error instanceof MemoryApiError && error.status === 422 ? '内容包含不可保存的信息，请修改后重试。' : safeMessage(editingId.value ? '记忆更新' : '记忆保存')
  } finally { formSaving.value = false }
  if (saved) closeForm()
}

async function focusAfterDelete(index: number) { await nextTick(); const adjacent = memories.value[index] ?? memories.value[index - 1]; (adjacent ? document.querySelector<HTMLButtonElement>(`[data-memory-id="${adjacent.id}"] .edit-button`) : addButton.value)?.focus() }
async function removeMemory(memory: UserMemory) {
  if (deletingId.value || formSaving.value) return
  const index = memories.value.findIndex(item => item.id === memory.id)
  deletingId.value = memory.id; deleteErrorId.value = null; actionError.value = ''
  try {
    const deleted = await runConfirmedMemoryDelete(() => window.confirm('确定要删除这条记忆吗？此操作无法撤销。'), () => deleteMemory(memory.id))
    if (!deleted) return
    memories.value = memories.value.filter(item => item.id !== memory.id); status.value = '记忆已删除。'; await focusAfterDelete(index)
  } catch { deleteErrorId.value = memory.id; actionError.value = safeMessage('记忆删除') } finally { deletingId.value = null }
}
onMounted(() => { void loadPreferences(); void loadMemories() })
onBeforeUnmount(() => { listCoordinator.invalidate(); preferenceRequests.invalidate() })
</script>

<template>
  <div class="page memory-page">
    <header class="page-head"><BackButton fallback="/settings" /><h2>我的记忆</h2></header>
    <p class="page-sub">查看、整理和删除福小禾为你长期保留的信息。</p>
    <p class="notice" role="note"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 3.5 19h17L12 3Z"/><path d="M12 9v4.5M12 17h.01"/></svg>请勿保存密码、验证码、访问令牌或其他凭证。</p>
    <section class="card auto-card" aria-labelledby="auto-memory-title">
      <div class="auto-copy"><h3 id="auto-memory-title">自动记忆</h3><p>开启后，福小禾会从已完成的对话中提取适合长期保留的信息。</p></div>
      <button type="button" class="toggle memory-toggle" :class="{ on: preferenceValue === true }" role="switch" :aria-checked="preferenceValue === true" aria-label="自动记忆" :disabled="!canTogglePreference" @click="toggleAutoCapture"><span class="knob" aria-hidden="true"></span></button>
      <span class="control-status">{{ preference.loading ? '正在加载…' : preferencesSaving ? '正在保存…' : preferenceValue === null ? '状态未知' : preferenceValue ? '已开启' : '已关闭' }}</span>
      <p v-if="preferenceError" class="operation-error" role="alert">{{ preferenceError }} <button type="button" :disabled="preferencesSaving" @click="retryPreferences">重试</button></p>
    </section>
    <section aria-labelledby="memory-list-title">
      <div class="section-head"><div><h3 id="memory-list-title">已保存的记忆</h3><p>选择分类来筛选内容。</p></div><button ref="addButton" type="button" class="add-button" :disabled="!canAddMemory || formSaving || !!deletingId" :aria-disabled="!canAddMemory || formSaving || !!deletingId" @click="openCreateForm($event)"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>添加记忆</button></div>
      <div class="chips" role="group" aria-label="记忆分类筛选"><button v-for="category in categories" :key="category.label" type="button" class="chip" :class="{ selected: selectedCategory === category.value }" :aria-pressed="selectedCategory === category.value" :disabled="initialLoading || loadingMore" @click="selectCategory(category.value)">{{ category.label }}</button></div>
      <div v-if="initialLoading" class="memory-list skeleton-list" aria-busy="true" aria-label="正在加载记忆"><div v-for="index in 3" :key="index" class="skeleton-card"><span></span><span></span></div></div>
      <div v-else-if="initialListError" class="state-card" role="alert"><p>{{ initialListError }}</p><button type="button" class="retry-button" @click="loadMemories()">重试加载</button></div>
      <div v-else-if="memories.length === 0" class="state-card empty-state"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h8l3 3v15H6V3h1Z"/><path d="M9 11h6M9 15h4"/></svg><p>还没有形成长期记忆</p><span>你可以手动添加一条，或开启自动记忆。</span><button type="button" class="retry-button" @click="openCreateForm($event)">添加记忆</button></div>
      <div v-else class="memory-list"><article v-for="memory in memories" :key="memory.id" class="memory-card" :data-memory-id="memory.id"><div class="memory-meta"><span class="category-tag">{{ categoryLabel(memory.category) }}</span><time :datetime="memory.updated_at">更新于 {{ new Date(memory.updated_at).toLocaleDateString('zh-CN') }}</time></div><p class="memory-content">{{ memory.content }}</p><div class="memory-actions"><button type="button" class="text-button edit-button" :disabled="formSaving || !!deletingId" @click="openEditForm(memory, $event)">编辑</button><button type="button" class="text-button danger" :disabled="formSaving || !!deletingId" @click="removeMemory(memory)">{{ deletingId === memory.id ? '删除中…' : '删除' }}</button></div><p v-if="deleteErrorId === memory.id" class="operation-error" role="alert">{{ actionError }} <button type="button" @click="removeMemory(memory)">重试删除</button></p></article></div>
      <div v-if="!initialLoading && !initialListError && (nextCursor || appendError)" class="more-area"><p v-if="appendError" class="operation-error" role="alert">{{ appendError }}</p><button v-if="nextCursor" type="button" class="load-more" :disabled="loadingMore" @click="loadMemories(true)">{{ loadingMore ? '正在加载更多…' : appendError ? '重试加载更多' : '加载更多' }}</button></div>
    </section>
    <dialog v-if="formOpen" ref="formDialog" class="card form-card" aria-labelledby="memory-form-title" @cancel="onDialogCancel" @close="onDialogClosed" @keydown="onDialogKeydown"><div class="form-head"><h3 id="memory-form-title">{{ editingId ? '编辑记忆' : '添加记忆' }}</h3><button type="button" class="close-button" aria-label="关闭记忆表单" :disabled="formSaving" @click="closeForm"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div><form @submit.prevent="submitForm"><div class="form-field"><label for="memory-category">分类</label><select id="memory-category" ref="categoryField" v-model="form.category" :disabled="formSaving"><option v-for="category in categories.slice(1)" :key="category.value" :value="category.value">{{ category.label }}</option></select></div><div class="form-field"><label for="memory-content">记忆内容</label><textarea id="memory-content" v-model="form.content" maxlength="500" rows="4" required :disabled="formSaving" :aria-invalid="Boolean(formError)" :aria-describedby="formError ? 'memory-content-help memory-content-error' : 'memory-content-help'"></textarea><span id="memory-content-help" class="field-help">最多 500 字；不要填写密码、验证码或访问令牌。</span><p v-if="formError" id="memory-content-error" class="field-error" role="alert">{{ formError }}</p></div><div class="form-field"><label for="memory-importance">重要程度：{{ Math.round(form.importance * 100) }}%</label><input id="memory-importance" v-model.number="form.importance" type="range" min="0" max="1" step="0.1" :disabled="formSaving" /></div><div class="form-actions"><button type="button" class="cancel-button" :disabled="formSaving" @click="closeForm">取消</button><button type="submit" class="save-button" :disabled="formSaving">{{ formSaving ? '正在保存…' : editingId ? '保存修改' : '保存记忆' }}</button></div></form></dialog>
    <p class="sr-status" aria-live="polite" aria-atomic="true">{{ status }}</p>
  </div>
</template>

<style scoped>
dialog.form-card { box-sizing: border-box; width: min(calc(100vw - var(--space-6)), 448px); margin: auto; }
dialog.form-card::backdrop { background: color-mix(in srgb, var(--brand-deep) 54%, transparent); }
</style>

<style scoped>
.memory-page { --memory-ink: var(--brand-deep); --memory-support: var(--text-secondary); gap: var(--space-4); padding-bottom: var(--space-6); overflow-x: hidden; }.memory-page :deep(.back) { width: 44px; height: 44px; }.page-sub,.auto-copy p,.section-head p,.control-status,.field-help,.memory-meta { color: var(--memory-support); }.page-sub { margin-top: calc(var(--space-2) * -1); line-height: 1.6; }.notice { display:flex; align-items:flex-start; gap:var(--space-2); padding:var(--space-3); border:1px solid var(--accent-purple); border-radius:var(--radius-md); background:var(--bg-green-faint); color:var(--memory-support); font-size:var(--text-sm); line-height:1.55; }.notice svg,.add-button svg,.close-button svg,.empty-state>svg { width:20px; height:20px; flex-shrink:0; fill:none; stroke:currentColor; stroke-width:1.8; stroke-linecap:round; stroke-linejoin:round; }.notice svg { color:var(--accent-purple); margin-top:1px; }.auto-card { display:grid; grid-template-columns:minmax(0,1fr) auto; gap:var(--space-2) var(--space-3); padding:var(--space-4); }.auto-copy h3,.section-head h3,.form-head h3 { font-size:var(--text-md); color:var(--text-primary); font-weight:var(--weight-semibold); }.auto-copy p,.section-head p { margin-top:var(--space-1); font-size:var(--text-sm); line-height:1.55; }.memory-toggle { min-width:46px; min-height:44px; height:44px; border:2px solid var(--memory-ink); padding:0; background:var(--bg-green-soft); }.memory-toggle.on { background:var(--memory-ink); }.memory-toggle .knob { top:8px; border:1px solid var(--memory-ink); }.memory-toggle.on .knob { left:20px; }.memory-toggle:disabled { cursor:not-allowed; opacity:.62; }.control-status,.operation-error { grid-column:1/-1; font-size:var(--text-sm); line-height:1.5; }.operation-error,.field-error { color:var(--accent-purple); font-weight:var(--weight-medium); }.operation-error button,.retry-button,.text-button,.load-more,.add-button,.cancel-button,.save-button,.close-button { font:inherit; cursor:pointer; }.operation-error button { display:inline-flex; min-width:44px; min-height:44px; align-items:center; justify-content:center; padding:var(--space-2) var(--space-3); border:1px solid var(--accent-purple); border-radius:var(--radius-full); background:var(--bg-surface); color:var(--accent-purple); font-weight:var(--weight-semibold); }.section-head { display:flex; align-items:flex-start; justify-content:space-between; gap:var(--space-3); margin-bottom:var(--space-3); }.add-button { display:inline-flex; min-width:44px; min-height:44px; align-items:center; justify-content:center; gap:var(--space-1); padding:var(--space-2) var(--space-3); border:2px solid var(--memory-ink); border-radius:var(--radius-full); background:var(--bg-green-faint); color:var(--memory-ink); font-size:var(--text-sm); font-weight:var(--weight-semibold); white-space:nowrap; }.add-button svg { width:17px; height:17px; }.chips,.memory-list { display:flex; flex-wrap:wrap; gap:var(--space-2); }.chips { margin-bottom:var(--space-3); }.chip { min-height:44px; padding:var(--space-2) var(--space-3); color:var(--memory-support); }.chip.selected { border-color:var(--memory-ink); color:var(--memory-ink); }.memory-list { flex-direction:column; }.memory-card,.state-card { border:1px solid var(--border); border-radius:var(--radius-lg); background:var(--bg-surface); padding:var(--space-4); }.memory-meta { display:flex; align-items:center; justify-content:space-between; gap:var(--space-2); font-size:var(--text-sm); }.category-tag { padding:3px var(--space-2); border-radius:var(--radius-full); background:var(--bg-green-soft); color:var(--memory-ink); font-weight:var(--weight-semibold); }.memory-meta time { white-space:nowrap; }.memory-content { margin:var(--space-3) 0; color:var(--text-primary); font-size:var(--text-base); line-height:1.65; overflow-wrap:anywhere; white-space:pre-wrap; }.memory-actions { display:flex; justify-content:flex-end; gap:var(--space-2); border-top:1px solid var(--bg-subtle); padding-top:var(--space-2); }.text-button { min-width:44px; min-height:44px; padding:var(--space-2) var(--space-3); border:1px solid var(--memory-ink); border-radius:var(--radius-full); background:var(--bg-surface); color:var(--memory-ink); font-size:var(--text-sm); }.text-button.danger { border-color:var(--accent-purple); color:var(--accent-purple); }.state-card { display:flex; flex-direction:column; align-items:center; gap:var(--space-2); text-align:center; color:var(--memory-support); font-size:var(--text-sm); line-height:1.55; }.empty-state>svg { width:32px; height:32px; color:var(--memory-ink); }.empty-state span { color:var(--memory-support); font-size:var(--text-sm); }.retry-button,.load-more { min-height:44px; padding:var(--space-2) var(--space-4); border:2px solid var(--memory-ink); border-radius:var(--radius-full); background:var(--bg-surface); color:var(--memory-ink); font-size:var(--text-sm); font-weight:var(--weight-semibold); }.more-area { margin-top:var(--space-3); }.more-area .operation-error { margin-bottom:var(--space-2); }.load-more { display:block; width:100%; }.skeleton-list { pointer-events:none; }.skeleton-card { overflow:hidden; padding:var(--space-4); border-radius:var(--radius-lg); background:var(--bg-green-faint); }.skeleton-card span { display:block; width:42%; height:14px; border-radius:var(--radius-full); background:var(--bg-green-soft); animation:pulse 200ms ease-in-out infinite alternate; }.skeleton-card span+span { width:86%; margin-top:var(--space-3); }.dialog-backdrop { position:fixed; inset:0; z-index:20; display:flex; align-items:flex-end; justify-content:center; padding:var(--space-4); background:color-mix(in srgb,var(--brand-deep) 54%,transparent); }.form-card { width:min(100%,448px); max-height:calc(100vh - var(--space-8)); overflow-y:auto; border:2px solid var(--memory-ink); box-shadow:0 12px 28px rgba(43,58,49,.28); }.form-head { display:flex; align-items:center; justify-content:space-between; gap:var(--space-3); margin-bottom:var(--space-4); }.close-button { display:grid; min-width:44px; min-height:44px; place-items:center; border:1px solid var(--memory-ink); border-radius:var(--radius-full); background:var(--bg-surface); color:var(--memory-ink); }.form-field textarea { min-height:104px; resize:vertical; line-height:1.55; }.form-field input[type='range'] { min-height:44px; padding:0; accent-color:var(--memory-ink); }.field-help,.field-error { font-size:var(--text-sm); line-height:1.5; }.field-error { margin-top:var(--space-1); }.form-actions { display:flex; justify-content:flex-end; gap:var(--space-2); }.cancel-button,.save-button { min-height:44px; padding:var(--space-2) var(--space-4); border-radius:var(--radius-md); font-size:var(--text-sm); font-weight:var(--weight-semibold); }.cancel-button { border:2px solid var(--memory-ink); background:var(--bg-surface); color:var(--memory-ink); }.save-button { border:2px solid var(--memory-ink); background:var(--memory-ink); color:var(--text-inverse); }.add-button:disabled,.text-button:disabled,.retry-button:disabled,.load-more:disabled,.cancel-button:disabled,.save-button:disabled,.close-button:disabled,.operation-error button:disabled { cursor:not-allowed; opacity:.56; }.memory-page button:focus-visible,.memory-page select:focus-visible,.memory-page textarea:focus-visible,.memory-page input:focus-visible,.form-card:focus-visible { outline:3px solid var(--memory-ink); outline-offset:3px; }.sr-status { position:absolute; width:1px; height:1px; padding:0; margin:-1px; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }@keyframes pulse { to { opacity:.52; transform:translateY(1px); } }@media (max-width:375px) { .memory-page { padding-left:var(--space-3); padding-right:var(--space-3); }.section-head { flex-direction:column; }.add-button { width:100%; }.memory-meta { align-items:flex-start; flex-direction:column; }.memory-meta time { white-space:normal; }.dialog-backdrop { padding:var(--space-3); } }@media (prefers-reduced-motion:reduce) { *,*::before,*::after { animation-duration:.01ms!important; animation-iteration-count:1!important; transition-duration:.01ms!important; scroll-behavior:auto!important; } }
</style>
