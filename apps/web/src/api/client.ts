const BASE = '/api/v1'
// 比 API 的 75 秒上限稍长：后端不可达时，浏览器也不能无限停留在“检索中”。
const CLIENT_STREAM_TIMEOUT_MS = 90_000

export interface Citation {
  citation_id: string
  document_title: string
  chunk_index: number
  excerpt: string
  trust_level: string
  source_url?: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  created_at: string
}

async function jsonResponse<T>(res: Response, fallback = '请求失败'): Promise<T> {
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || data.message || fallback)
  }
  return data as T
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE}/conversations`, { headers: authHeaders() })
  return jsonResponse<Conversation[]>(res, '会话列表加载失败')
}

export async function fetchMessages(convId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${BASE}/conversations/${convId}/messages`, { headers: authHeaders() })
  return jsonResponse<ChatMessage[]>(res, '消息记录加载失败')
}

export function sendMessage(
  message: string,
  threadId: string | null,
  onNode: (node: string, msg: string) => void,
  onToken: (text: string) => void,
  onCitation: (cit: Citation) => void,
  onFinal: (data: any) => void,
  onError: (err: string) => void,
  intent = 'policy',
): AbortController {
  const controller = new AbortController()
  let timeoutTriggered = false
  let reportedError = false
  const timeoutId = window.setTimeout(() => {
    timeoutTriggered = true
    controller.abort()
    reportError('连接服务器超时，请检查网络后重试')
  }, CLIENT_STREAM_TIMEOUT_MS)

  function reportError(message: string) {
    if (reportedError) return
    reportedError = true
    onError(message)
  }

  void (async () => {
    try {
      const res = await fetch(`${BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ message, thread_id: threadId, intent }),
        signal: controller.signal,
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        reportError(data.detail || data.message || '消息发送失败')
        return
      }
      const convId = res.headers.get('X-Conversation-Id')
      const reader = res.body?.getReader()
      if (!reader) {
        reportError('服务器未返回有效响应')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''
      let receivedFinal = false
      let receivedError = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              const ev = currentEvent
              currentEvent = ''

              if (ev === 'node_update') {
                onNode(data.node, data.message)
              } else if (ev === 'token') {
                onToken(data.content)
              } else if (ev === 'citation') {
                onCitation(data as Citation)
              } else if (ev === 'final') {
                receivedFinal = true
                onFinal({ ...data, conversation_id: convId })
              } else if (ev === 'error') {
                receivedError = true
                reportError(data.message)
              }
            } catch { /* partial chunk */ }
          }
        }
      }
      if (!receivedFinal && !receivedError) reportError('服务器提前结束了响应，请重试')
    } catch (err) {
      if (!timeoutTriggered && (err as { name?: string }).name !== 'AbortError') {
        reportError((err as Error).message || '消息发送失败')
      }
    } finally {
      window.clearTimeout(timeoutId)
    }
  })()

  return controller
}

// ── 规划域 / 画像域 API ──────────────────────────────

export interface StudentProfile {
  id: string
  major: string
  grade: string
  campus: string
  interests: string[]
  strengths: string[]
  career_goals: string
  math_willingness: boolean
  campus_flexibility: boolean
  credit_budget: number
  certificate_goal: string
  schedule_preferences: Record<string, unknown>
  version: number
  updated_at: string | null
}

export interface ProfileOptions {
  version: number
  interests: string[]
  strengths: string[]
}

export interface ProfileInput {
  major: string
  grade: string
  campus?: string
  interests?: string[]
  strengths?: string[]
  career_goals?: string
  math_willingness?: boolean
  campus_flexibility?: boolean
  credit_budget?: number
  certificate_goal?: string
  schedule_preferences?: Record<string, unknown>
}

export interface Program {
  name: string
  total_credits: number
  campus: string
  subject_rank: string
  core_courses: string[]
  required_math: boolean
  required_math_level: string
  semesters_needed: number
  discipline: string
  course_count: number
  participant_count: number
  catalog_version: string
  source_url: string
  has_plan?: boolean
}

export interface Recommendation {
  program: Program
  scores: Record<string, number>
  total_score: number
  risks: string[]
}

export interface PlanItem {
  semester: number
  term: string
  year: number
  course: string
  credits: number
  campus: string
  course_code?: string
  category?: string
  official_term?: string
  source_url?: string
}

export interface PlanResult {
  program: string
  items: PlanItem[]
  alternatives: PlanItem[][]
  warnings: string[]
  infeasible: boolean
}

export interface Job {
  id: string
  employer: string
  title: string
  location: string
  majors: string[]
  preferred_cross: string[]
  skills_required: string[]
  skills_preferred: string[]
  deadline: string
  source: string
  source_url?: string
  data_status?: string
}

export interface LearningProgress {
  completed_credits: number
  in_progress_credits: number
  planned_credits: number
  total_credits: number
  learning_days: number
  streak_days: number
  target_credits: number
  completion_percent: number
  plan_program: string | null
  records: Array<Record<string, unknown>>
}

export async function fetchProfile(): Promise<StudentProfile | null> {
  const res = await fetch(`${BASE}/profile`, { headers: authHeaders() })
  if (res.status === 401) return null
  const data = await jsonResponse<{ profile?: StudentProfile }>(res, '学生画像加载失败')
  return data.profile ?? null
}

export async function fetchProfileOptions(): Promise<ProfileOptions> {
  const res = await fetch(`${BASE}/profile/options`, { headers: authHeaders() })
  return jsonResponse<ProfileOptions>(res, '画像选项加载失败')
}

export async function fetchAvatar(): Promise<Blob | null> {
  const res = await fetch(`${BASE}/profile/avatar`, { headers: authHeaders(), cache: 'no-store' })
  if (res.status === 404) return null
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || '头像加载失败')
  }
  return res.blob()
}

export async function uploadAvatar(file: File): Promise<{ size_bytes: number; content_type: string; updated_at: string | null }> {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(`${BASE}/profile/avatar`, {
    method: 'POST',
    headers: authHeaders(),
    body,
  })
  const data = await jsonResponse<{ avatar: { size_bytes: number; content_type: string; updated_at: string | null } }>(res, '头像上传失败')
  return data.avatar
}

export async function saveProfile(input: ProfileInput): Promise<StudentProfile> {
  const res = await fetch(`${BASE}/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(input),
  })
  const data = await jsonResponse<{ profile: StudentProfile }>(res, '学生画像保存失败')
  return data.profile
}

// partial-merge：onboarding 页只传自己采集的字段，不覆盖其余字段
export async function updateProfile(partial: Partial<ProfileInput>): Promise<StudentProfile> {
  const e = await fetchProfile()
  return saveProfile({
    major: partial.major ?? e?.major ?? '',
    grade: partial.grade ?? e?.grade ?? '大二',
    campus: partial.campus ?? e?.campus ?? '',
    interests: partial.interests ?? e?.interests ?? [],
    strengths: partial.strengths ?? e?.strengths ?? [],
    career_goals: partial.career_goals ?? e?.career_goals ?? '',
    math_willingness: partial.math_willingness ?? e?.math_willingness ?? false,
    campus_flexibility: partial.campus_flexibility ?? e?.campus_flexibility ?? false,
    credit_budget: partial.credit_budget ?? e?.credit_budget ?? 0,
    certificate_goal: partial.certificate_goal ?? e?.certificate_goal ?? '',
    schedule_preferences: { ...(e?.schedule_preferences ?? {}), ...(partial.schedule_preferences ?? {}) },
  })
}

export async function fetchPrograms(): Promise<Program[]> {
  const res = await fetch(`${BASE}/programs`)
  const data = await jsonResponse<{ programs: Program[] }>(res, '专业目录加载失败')
  return data.programs
}

export async function recommendPrograms(profile?: ProfileInput): Promise<Recommendation[]> {
  const res = await fetch(`${BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(profile ? { profile } : {}),
  })
  const data = await jsonResponse<{ recommendations: Recommendation[] }>(res, '推荐生成失败')
  return data.recommendations
}

export async function fetchPlan(program: string): Promise<PlanResult> {
  const res = await fetch(`${BASE}/programs/plan?program=${encodeURIComponent(program)}`, { headers: authHeaders() })
  const data = await jsonResponse<PlanResult>(res, '培养方案加载失败')
  return data
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${BASE}/jobs`)
  const data = await jsonResponse<{ jobs: Job[] }>(res, '岗位列表加载失败')
  return data.jobs
}

export async function fetchJob(id: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${id}`)
  const data = await jsonResponse<{ job: Job }>(res, '岗位详情加载失败')
  return data.job
}

export async function fetchLearningProgress(): Promise<LearningProgress> {
  const res = await fetch(`${BASE}/learning/progress`, { headers: authHeaders() })
  return jsonResponse<LearningProgress>(res, '学习进度加载失败')
}

export async function fetchFavoriteJobIds(): Promise<string[]> {
  const res = await fetch(`${BASE}/favorites/jobs`, { headers: authHeaders() })
  const data = await jsonResponse<{ job_ids: string[] }>(res, '岗位收藏加载失败')
  return data.job_ids ?? []
}

export async function addFavoriteJob(id: string): Promise<void> {
  const res = await fetch(`${BASE}/favorites/jobs/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: authHeaders(),
  })
  await jsonResponse(res, '岗位收藏失败')
}

export async function removeFavoriteJob(id: string): Promise<void> {
  const res = await fetch(`${BASE}/favorites/jobs/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  await jsonResponse(res, '取消收藏失败')
}

export type UserPreferences = Record<string, unknown>

export async function fetchPreferences(): Promise<UserPreferences> {
  const res = await fetch(`${BASE}/preferences`, { headers: authHeaders() })
  const data = await jsonResponse<{ preferences: UserPreferences }>(res, '偏好设置加载失败')
  return data.preferences ?? {}
}

export async function savePreferences(preferences: UserPreferences): Promise<UserPreferences> {
  const res = await fetch(`${BASE}/preferences`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ preferences }),
  })
  const data = await jsonResponse<{ preferences: UserPreferences }>(res, '偏好设置保存失败')
  return data.preferences ?? {}
}

export async function submitFeedback(payload: {
  feedback_type: string
  content: string
  contact?: string
  attachments?: string[]
}): Promise<{ id: string; status: string }> {
  const res = await fetch(`${BASE}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(payload),
  })
  return jsonResponse<{ id: string; status: string }>(res, '反馈提交失败')
}

export interface SearchResult {
  chunk_id: string
  content: string
  document_title: string
  trust_level: string
  score: number
}

export async function searchKnowledge(q: string): Promise<{ query: string; results: SearchResult[]; citations: Citation[] }> {
  const res = await fetch(`${BASE}/knowledge/search?q=${encodeURIComponent(q)}`, { headers: authHeaders() })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '检索失败')
  return data
}

// ── 账号 API ──────────────────────────────

export interface AuthUser {
  id: string
  username: string
  nickname: string
  onboarding_completed: boolean
}

export interface AuthResponse {
  token: string
  user: AuthUser
}

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('fxh_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function authRequest(path: string, body?: Record<string, string>): Promise<any> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '请求失败')
  return data
}

export function register(username: string, password: string, nickname: string): Promise<AuthResponse> {
  return authRequest('/auth/register', { username, password, nickname })
}

export function login(username: string, password: string): Promise<AuthResponse> {
  return authRequest('/auth/login', { username, password })
}

export async function updateOnboardingStatus(completed: boolean): Promise<boolean> {
  const res = await fetch(`${BASE}/auth/onboarding`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ completed }),
  })
  const data = await jsonResponse<{ onboarding_completed: boolean }>(res, '引导状态保存失败')
  return data.onboarding_completed
}

export function logout(): Promise<{ status: string }> {
  return authRequest('/auth/logout')
}

export function changePassword(old_password: string, new_password: string): Promise<{ status: string }> {
  return authRequest('/auth/change-password', { old_password, new_password })
}

export async function updateNickname(nickname: string): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/nickname`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ nickname }),
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '修改失败')
  return data.user
}

export async function me(): Promise<AuthUser> {
  const res = await fetch(`${BASE}/auth/me`, { headers: authHeaders() })
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '未登录')
  return data.user
}
