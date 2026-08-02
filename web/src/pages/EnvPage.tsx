import { api } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Server, Info } from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import { Skeleton } from "@/components/ui/skeleton"
import { DetailSkeleton } from "@/components/shared/PageSkeletons"
import type { EnvData } from "@/types"

export default function EnvPage() {
  const { data, loading } = usePolling(() => api.env(), 30000)

  const env: EnvData | null = data

  if (loading && !env) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-4 w-56" />
        </div>
        <DetailSkeleton />
      </div>
    )
  }

  if (!env) return null

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Env 查看</h1>
        <p className="text-sm text-muted-foreground">环境配置文件内容</p>
      </div>

      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>{env.message}</AlertDescription>
      </Alert>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Server className="h-4 w-4" />
            .env 文件
            <Badge variant={env.environment === "vercel" ? "secondary" : "default"}>
              {env.environment}
            </Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            路径: {env.path} | 存在: {env.exists ? "是" : "否"}
          </p>
        </CardHeader>
        <CardContent>
          {env.content ? (
            <pre className="overflow-x-auto rounded-md bg-muted p-4 font-mono text-xs leading-relaxed">
              {env.content}
            </pre>
          ) : (
            <p className="py-8 text-center text-muted-foreground">
              {env.environment === "vercel"
                ? "Vercel 环境下无法直接查看 .env 文件，请到 Vercel 项目 Settings → Environment Variables 查看"
                : ".env 文件不存在"}
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
