import { usePolling } from "@/hooks/use-polling"
import { api } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Server,
  KeyRound,
  Activity,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react"
import type { OverviewData } from "@/types"

function StatCard({
  title,
  value,
  icon: Icon,
  badge,
}: {
  title: string
  value: string | number
  icon: React.ComponentType<{ className?: string }>
  badge?: { text: string; variant: "default" | "secondary" | "destructive" | "outline" }
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-muted-foreground">{title}</p>
          <div className="flex items-center gap-2">
            <p className="text-xl font-semibold">{value}</p>
            {badge && (
              <Badge variant={badge.variant} className="text-xs">
                {badge.text}
              </Badge>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function StatsSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
        <Card key={i}>
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <Skeleton className="h-10 w-10 rounded-lg" />
              <div className="flex-1">
                <Skeleton className="mb-2 h-4 w-20" />
                <Skeleton className="h-6 w-16" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default function DashboardPage() {
  const { data, loading, error } = usePolling(() => api.overview(), 15000)

  if (loading && !data) return <StatsSkeleton />

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20">
        <AlertTriangle className="h-12 w-12 text-destructive" />
        <p className="text-muted-foreground">加载失败: {error}</p>
      </div>
    )
  }

  if (!data) return null

  const stats: OverviewData = data

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">概览</h1>
        <p className="text-sm text-muted-foreground">服务运行状态一览</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="服务状态"
          value={stats.status === "ok" ? "运行中" : "异常"}
          icon={stats.status === "ok" ? CheckCircle2 : AlertTriangle}
          badge={{
            text: stats.environment,
            variant: stats.environment === "vercel" ? "secondary" : "default",
          }}
        />
        <StatCard
          title="Token 账号"
          value={stats.account_count}
          icon={KeyRound}
        />
        <StatCard
          title="可用模型"
          value={stats.model_count}
          icon={Server}
        />
        <StatCard
          title="日志等级"
          value={stats.log_level}
          icon={Activity}
          badge={{
            text: stats.debug ? "Debug" : "Normal",
            variant: stats.debug ? "destructive" : "outline",
          }}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">详细信息</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-3 sm:grid-cols-2">
            <div className="flex items-center justify-between rounded-md border p-3">
              <dt className="text-sm text-muted-foreground">上游 API</dt>
              <dd className="font-mono text-sm">{stats.base_url}</dd>
            </div>
            <div className="flex items-center justify-between rounded-md border p-3">
              <dt className="text-sm text-muted-foreground">部署环境</dt>
              <dd>
                <Badge variant={stats.environment === "vercel" ? "secondary" : "default"}>
                  {stats.environment}
                </Badge>
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}
