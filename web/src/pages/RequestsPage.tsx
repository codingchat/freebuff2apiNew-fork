import { useState, useCallback } from "react"
import { api } from "@/lib/api-client"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { RefreshCw, Trash2 } from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import { Skeleton } from "@/components/ui/skeleton"
import { TableSkeleton } from "@/components/shared/PageSkeletons"
import type { RequestsData, RequestRecord } from "@/types"

export default function RequestsPage() {
  const [filter, setFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [clearing, setClearing] = useState(false)

  const fetcher = useCallback(
    () =>
      api.requests({
        limit: 200,
        status: statusFilter || undefined,
        api_key_name: filter || undefined,
      }),
    [statusFilter, filter],
  )
  const { data, loading, refresh } = usePolling(fetcher, 10000)

  const reqData: RequestsData | null = data
  const items: RequestRecord[] = reqData?.items || []

  if (loading && !reqData) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-36" />
            <Skeleton className="h-4 w-24" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-9 w-40" />
            <Skeleton className="h-9 w-28" />
            <Skeleton className="h-9 w-20" />
            <Skeleton className="h-9 w-20" />
          </div>
        </div>
        <TableSkeleton rows={6} columns={7} />
      </div>
    )
  }

  const handleClear = async () => {
    if (!confirm("确定清空所有请求记录？")) return
    setClearing(true)
    try {
      await api.clearRequests()
      refresh()
    } catch {
      alert("清空失败")
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">请求记录</h1>
          <p className="text-sm text-muted-foreground">共 {items.length} 条</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Input
            placeholder="API Key 名称"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full sm:w-40"
          />
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? "")}>
            <SelectTrigger className="w-28">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="success">成功</SelectItem>
              <SelectItem value="error">失败</SelectItem>
            </SelectContent>
          </Select>
          <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
            <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={handleClear}
            disabled={clearing}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            清空
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {items.length === 0 ? (
            <div className="py-20 text-center text-muted-foreground">暂无请求记录</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="px-4 py-3 font-medium">时间</th>
                    <th className="px-4 py-3 font-medium">状态</th>
                    <th className="px-4 py-3 font-medium">模型</th>
                    <th className="px-4 py-3 font-medium">API Key</th>
                    <th className="px-4 py-3 font-medium">耗时</th>
                    <th className="px-4 py-3 font-medium">Token</th>
                    <th className="px-4 py-3 font-medium">错误</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id} className="border-b border-border hover:bg-muted/50">
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted-foreground">
                        {r.timestamp}
                      </td>
                      <td className="px-4 py-2">
                        <Badge variant={r.status === "success" ? "default" : "destructive"}>
                          {r.status}
                        </Badge>
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 font-mono text-xs">
                        {r.model}
                      </td>
                      <td className="px-4 py-2 text-xs">{r.api_key_name}</td>
                      <td className="whitespace-nowrap px-4 py-2 text-xs">
                        {r.duration_ms}ms
                      </td>
                      <td className="whitespace-nowrap px-4 py-2 text-xs">
                        {r.total_tokens}
                      </td>
                      <td className="max-w-xs break-words whitespace-normal px-4 py-2 text-xs text-destructive">
                        {r.error || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
