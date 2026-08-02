import type { ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { usePolling } from "@/hooks/use-polling"
import { api } from "@/lib/api-client"
import type { OverviewData, RequestStats } from "@/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Activity, AlertTriangle, ArrowRight, CheckCircle2, Clock,
  FileText, Key, Pencil, Plus, Server, Shield, XCircle,
} from "lucide-react"

interface StatCardProps {
  icon: ReactNode
  title: string
  value: ReactNode
  detail?: ReactNode
  loading: boolean
}

function StatCard({ icon, title, value, detail, loading }: StatCardProps) {
  return (
    <Card className="border-border/60 shadow-sm">
      <CardContent className="pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium text-muted-foreground">{title}</p>
            {loading ? (
              <Skeleton className="mt-2 h-7 w-24" />
            ) : (
              <div className="mt-1 truncate text-2xl font-bold tracking-tight">{value}</div>
            )}
          </div>
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">{icon}</div>
        </div>
        {loading ? <Skeleton className="mt-3 h-4 w-32" /> : detail ? <div className="mt-2 text-xs text-muted-foreground">{detail}</div> : null}
      </CardContent>
    </Card>
  )
}

function ActivityMetric({ label, value, tone = "default" }: { label: string; value: ReactNode; tone?: "default" | "success" | "destructive" | "warning" }) {
  const cls = { default: "text-foreground", success: "text-success", destructive: "text-destructive", warning: "text-warning" }[tone]
  return (
    <div className="rounded-lg border border-border/60 bg-muted/25 px-3 py-2.5">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={`mt-1 text-lg font-semibold ${cls}`}>{value}</p>
    </div>
  )
}

function RecentActivityCard({ stats, loading }: { stats?: RequestStats; loading: boolean }) {
  const total = stats?.total ?? 0
  const success = stats?.success ?? 0
  const error = stats?.error ?? 0
  const successPercent = total > 0 ? Math.round((success / total) * 100) : 0
  const errorPercent = total > 0 ? Math.round((error / total) * 100) : 0
  const quietPercent = Math.max(100 - successPercent - errorPercent, 0)

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Activity className="size-4 text-primary" />请求统计
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="space-y-3">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <ActivityMetric label="总请求" value={total} />
              <ActivityMetric label="成功" value={success} tone="success" />
              <ActivityMetric label="失败" value={error} tone="destructive" />
              <ActivityMetric label="总 Token" value={stats?.total_tokens ?? 0} tone="warning" />
              <ActivityMetric label="平均耗时" value={stats?.avg_duration_ms ? `${stats.avg_duration_ms}ms` : "-"} />
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>成功率 {successPercent}%</span>
                <span>失败率 {errorPercent}%</span>
              </div>
              <div className="flex h-2 overflow-hidden rounded-full bg-muted">
                <div className="bg-success" style={{ width: `${successPercent}%` }} />
                <div className="bg-destructive" style={{ width: `${errorPercent}%` }} />
                <div className="bg-muted-foreground/15" style={{ width: `${quietPercent}%` }} />
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function ByModelCard({ stats, loading }: { stats?: RequestStats; loading: boolean }) {
  const navigate = useNavigate()
  const byModel = stats?.by_model ?? {}
  const entries = Object.entries(byModel).sort((a, b) => b[1].count - a[1].count)

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-1">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Server className="size-4 text-primary" />按模型分布
          </CardTitle>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => navigate("/admin/requests")}>
            请求记录 <ArrowRight className="ml-1 size-3" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? <Skeleton className="h-20 w-full" /> : entries.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">暂无请求数据</p>
        ) : (
          <div className="space-y-2">
            {entries.map(([model, data]) => (
              <div key={model} className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2 text-xs">
                <span className="font-mono truncate flex-1 mr-2">{model}</span>
                <div className="flex items-center gap-3 text-muted-foreground">
                  <span>{data.count} 次</span>
                  <span>{data.total_tokens} tokens</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function ModelAvailabilityCard({ overview, loading }: { overview?: OverviewData | null; loading: boolean }) {
  const rows = overview?.model_availability ?? []
  const accountCount = overview?.account_count ?? 0

  const cellStyle = (status: string, remaining: number) => {
    if (status === "blocked") {
      const secs = Math.max(0, Math.round(remaining))
      const m = Math.floor(secs / 60)
      const s = secs % 60
      return {
        cls: "bg-destructive/15 text-destructive",
        title: `限流中 · 冷却 ${m > 0 ? `${m}分${s}秒` : `${s}秒`}`,
      }
    }
    if (status === "invalid") return { cls: "bg-muted text-muted-foreground", title: "失效" }
    if (status === "checking") return { cls: "bg-primary/10 text-primary", title: "验证中" }
    return { cls: "bg-success-muted/30 text-success", title: "可用" }
  }

  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Server className="size-4 text-primary" />模型可用情况
          {!loading && rows.length > 0 && (
            <Badge variant="outline" className="ml-1 text-[10px]">
              {rows.length} 模型 × {accountCount} 账号
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : rows.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">暂无账号数据</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] border-collapse text-[11px] sm:text-xs">
              <thead>
                <tr className="border-b border-border/60">
                  <th className="py-1.5 pr-3 text-left font-medium text-muted-foreground">模型</th>
                  {Array.from({ length: accountCount }, (_, i) => (
                    <th key={i} className="px-1.5 py-1.5 text-center font-medium text-muted-foreground">
                      #{i + 1}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.model} className="border-b border-border/40 last:border-0">
                    <td className="py-1.5 pr-3">
                      <code className="font-mono text-[11px] text-muted-foreground">{row.model}</code>
                    </td>
                    {row.accounts.map((acc) => {
                      const { cls, title } = cellStyle(acc.status, acc.block_remaining)
                      return (
                        <td key={acc.index} className="px-1 py-1.5 text-center">
                          <div
                            className={`mx-auto h-5 w-5 rounded-md ${cls} ${acc.is_current ? "ring-1 ring-primary/50" : ""}`}
                            title={`${title}${acc.is_current ? " · 当前账号" : ""}`}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && rows.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded bg-success-muted/30 ring-1 ring-success/40" />可用</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded bg-destructive/15 ring-1 ring-destructive/40" />限流冷却</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded bg-muted ring-1 ring-border" />失效</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded bg-primary/10 ring-1 ring-primary/40" />验证中</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function QuickActionsCard() {
  const navigate = useNavigate()
  const actions = [
    { label: "管理 Token", icon: <Pencil className="size-4" />, onClick: () => navigate("/admin/token") },
    { label: "创建 API Key", icon: <Plus className="size-4" />, onClick: () => navigate("/admin/keys") },
    { label: "请求记录", icon: <FileText className="size-4" />, onClick: () => navigate("/admin/requests") },
    { label: "运行日志", icon: <AlertTriangle className="size-4" />, onClick: () => navigate("/admin/logs") },
  ]
  return (
    <Card className="border-border/60 shadow-sm">
      <CardHeader className="pb-1">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <ArrowRight className="size-4 text-primary" />快捷操作
        </CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-2 gap-2">
        {actions.map((action) => (
          <Button key={action.label} variant="outline" size="sm" className="h-9 justify-start text-xs" onClick={action.onClick}>
            {action.icon}{action.label}
          </Button>
        ))}
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const { data: overviewData, loading: overviewLoading, error: overviewError } = usePolling(() => api.overview(), 30000)
  const { data: statsData, loading: statsLoading } = usePolling(() => api.requestStats(), 30000)

  const overview: OverviewData | null = overviewData
  const stats: RequestStats | null = statsData
  const loading = overviewLoading

  return (
    <div className="mx-auto w-full max-w-[1320px] space-y-5">
      {overviewError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3 text-sm text-destructive">加载失败：{overviewError}</div>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={<CheckCircle2 className="size-4" />} title="服务状态" value={overview?.status === "ok" ? "运行中" : "异常"}
          detail={<Badge variant={overview?.environment === "vercel" ? "secondary" : "default"}>{overview?.environment}</Badge>}
          loading={loading} />
        <StatCard icon={<Key className="size-4" />} title="Token 账号" value={overview?.account_count ?? "-"} detail="Freebuff 上游账号池" loading={loading} />
        <StatCard icon={<Shield className="size-4" />} title="可用模型" value={overview?.model_count ?? "-"} detail={`上游: ${overview?.base_url ?? "-"}`} loading={loading} />
        <StatCard icon={<Clock className="size-4" />} title="日志等级" value={overview?.log_level ?? "-"}
          detail={<Badge variant={overview?.debug ? "destructive" : "outline"}>{overview?.debug ? "Debug" : "Normal"}</Badge>} loading={loading} />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <RecentActivityCard stats={stats ?? undefined} loading={statsLoading} />
          <ByModelCard stats={stats ?? undefined} loading={statsLoading} />
          <ModelAvailabilityCard overview={overview ?? undefined} loading={loading} />
        </div>
        <div className="space-y-5">
          <QuickActionsCard />
          <Card className="border-border/60 shadow-sm">
            <CardHeader className="pb-1">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <Activity className="size-4 text-warning" />请求概览
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-success-muted/30 px-3 py-2 text-success">
                  <CheckCircle2 className="mb-1 size-4" />{stats?.success ?? 0} 条成功
                </div>
                <div className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">
                  <XCircle className="mb-1 size-4" />{stats?.error ?? 0} 条失败
                </div>
              </div>
              <div className="mt-3 text-center text-2xl font-bold">{stats?.total ?? 0}</div>
              <p className="text-center text-xs text-muted-foreground">总请求数</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
