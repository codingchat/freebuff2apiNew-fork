export interface ApiResponse<T = unknown> {
  code: number
  msg: string
  data: T
}

export interface SessionInfo {
  authenticated: boolean
  admin_key_configured: boolean
  api_key_configured: boolean
  using_default_admin_key: boolean
}

export interface ConfigPayload {
  environment: string
  token_count: number
  tokens: TokenRow[]
  api_key_configured: boolean
  api_key_masked: string
  admin_key_configured: boolean
  admin_key_masked: string
  using_default_admin_key: boolean
  setup_complete: boolean
  debug: boolean
  log_level: string
  proxy_enabled: boolean
  proxy_type: string
  proxy_host: string
  proxy_port: number
  proxy_username: string
  proxy_display: string
  base_url: string
  port: number
}

export interface TokenRow {
  index: number
  masked: string
  prefix: string
  length: number
}

export interface OverviewData {
  status: string
  environment: string
  account_count: number
  model_count: number
  base_url: string
  debug: boolean
  log_level: string
}

export interface EnvData {
  environment: string
  path: string
  exists: boolean
  content: string
  editable: boolean
  message: string
}

export interface ModelItem {
  id: string
  object: string
  created: number
  owned_by: string
}

export interface ModelsResponse {
  object: string
  data: ModelItem[]
}

export interface LogItem {
  id: number
  time: string
  level: string
  logger: string
  message: string
  detail: string
}

export interface LogsData {
  items: LogItem[]
  limit: number
}

export interface RegionInfo {
  ok: boolean
  source: string
  latency_ms?: number
  ip?: string
  country?: string
  region?: string
  city?: string
  timezone?: string
  org?: string
  errors?: Array<{ source: string; error: string }>
}

export interface ConnectivityItem {
  name: string
  ok: boolean
  status?: number
  latency_ms?: number
  error?: string
}

export interface NetworkData {
  region: RegionInfo
  connectivity: ConnectivityItem[]
  proxy_enabled: boolean
  proxy_display: string
}

export interface TokenDetail {
  index: number
  token: string
  masked: string
}

export interface TokenVerifyResult {
  ok: boolean
  info: string
  upstream?: unknown
}

export interface ApiKeyItem {
  name: string
  key: string
  key_prefix: string
  allowed_models: string[]
  enabled: boolean
  created_at: string
}

export interface ApiKeysData {
  items: ApiKeyItem[]
  count: number
  active_count: number
}

export interface RequestRecord {
  id: number
  timestamp: string
  api_key_name: string
  api_key_prefix: string
  model: string
  duration_ms: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  status: string
  error: string | null
  client_ip: string | null
}

export interface RequestsData {
  items: RequestRecord[]
  limit: number
}

export interface RequestStats {
  total: number
  success: number
  error: number
  total_tokens: number
  total_prompt_tokens: number
  total_completion_tokens: number
  avg_duration_ms: number
  by_model: Record<string, { count: number; total_tokens: number }>
}

export interface ChatTestResult {
  ok: boolean
  response?: unknown
  info?: string
}

export interface ApiError {
  detail?: string
  error?: string
}
