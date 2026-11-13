export interface Profile {
  account: string
  password: string
  nick: string
  color: string
  avatarUrl: string
}

export interface TaskStep {
  id: number
  title: string
  done: boolean
}

export interface Task {
  id: number
  title: string
  date: string
  done: boolean
  doneAt?: string
  desc?: string
  note?: string
  sourceText?: string
  generated?: boolean
  todo_id?: string
  source_ref?: unknown
  steps?: TaskStep[]
  [key: string]: unknown
}

export interface AnalysisResult {
  id?: string
  matter_id?: string
  title?: string
  enabled_sections?: string[]
  deadline?: {
    due_at?: string
    start_at?: string
    end_at?: string
  }
  todo_list?: Array<{
    action?: string
    title?: string
    name?: string
    due_at?: string
    status?: string
    todo_id?: string
    source_ref?: unknown
  }>
  step_list?: AnalysisResult['todo_list']
  [key: string]: unknown
}

export type Matter = AnalysisResult

export interface ApiEnvelope<T> {
  success: boolean
  data?: T
  error?: string | ApiErrorDetail | null
  error_code?: string
  request_id?: string
}

export interface ApiErrorDetail {
  code?: string
  message?: string
  details?: unknown
}

export interface ApiErrorPayload {
  error?: string | ApiErrorDetail | null
  error_code?: string
  request_id?: string
}

export type AnalysisStageKey = 'preparing' | 'upload' | 'extract' | 'llm' | 'schema' | 'date' | 'complete'

export type ActiveTab = 'doing' | 'done' | 'history'

export interface AppState {
  profile: Profile
  tasks: Task[]
  analyzing: boolean
  analyzeError: import('./errors.ts').AppError | null
  analyzeResult: AnalysisResult | null
  resultFromImage?: boolean
  activeTab: ActiveTab
  focusDate?: string
  analysisStage: AnalysisStageKey
  analysisSlow: boolean
  analysisNotice: string
  compareMatter?: AnalysisResult | null
  comparePreviewTodo?: unknown[]
  onUpdate?: ((keys: string[]) => void) | null
}
