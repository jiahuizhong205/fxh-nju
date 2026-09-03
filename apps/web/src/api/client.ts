const BASE = '/api/v1'

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

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${BASE}/conversations`)
  return res.json()
}

export async function fetchMessages(convId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${BASE}/conversations/${convId}/messages`)
  return res.json()
}

export function sendMessage(
  message: string,
  threadId: string | null,
  onNode: (node: string, msg: string) => void,
  onToken: (text: string) => void,
  onCitation: (cit: Citation) => void,
  onFinal: (data: any) => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()

  fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal: controller.signal,
  }).then(async (res) => {
    const convId = res.headers.get('X-Conversation-Id')
    const reader = res.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buffer = ''

    let currentEvent = ''

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
              onFinal({ ...data, conversation_id: convId })
            } else if (ev === 'error') {
              onError(data.message)
            }
          } catch { /* partial chunk */ }
        }
      }
    }
  }).catch(err => {
    if (err.name !== 'AbortError') {
      onError(err.message)
    }
  })

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
}

export async function fetchProfile(): Promise<StudentProfile | null> {
  const res = await fetch(`${BASE}/profile`, { headers: authHeaders() })
  const data = await res.json()
  return data.profile ?? null
}

export async function saveProfile(input: ProfileInput): Promise<StudentProfile> {
  const res = await fetch(`${BASE}/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(input),
  })
  const data = await res.json()
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
  const data = await res.json()
  return data.programs
}

export async function recommendPrograms(profile?: ProfileInput): Promise<Recommendation[]> {
  const res = await fetch(`${BASE}/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile ? { profile } : {}),
  })
  const data = await res.json()
  return data.recommendations
}

export async function fetchPlan(program: string): Promise<PlanResult> {
  const res = await fetch(`${BASE}/programs/plan?program=${encodeURIComponent(program)}`)
  const data = await res.json()
  return data
}

export async function fetchJobs(): Promise<Job[]> {
  const res = await fetch(`${BASE}/jobs`)
  const data = await res.json()
  return data.jobs
}

export async function fetchJob(id: string): Promise<Job> {
  const res = await fetch(`${BASE}/jobs/${id}`)
  const data = await res.json()
  return data.job
}

export interface SearchResult {
  chunk_id: string
  content: string
  document_title: string
  trust_level: string
  score: number
}

export async function searchKnowledge(q: string): Promise<{ query: string; results: SearchResult[]; citations: Citation[] }> {
  const res = await fetch(`${BASE}/knowledge/search?q=${encodeURIComponent(q)}`)
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || '检索失败')
  return data
}

// ── 账号 API ──────────────────────────────

export interface AuthUser {
  id: string
  username: string
  nickname: string
}

export interface AuthResponse {
  token: string
  user: AuthUser
}

function authHeaders(): Record<string, string> {
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
