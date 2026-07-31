import { api } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Globe, RefreshCw, Wifi, WifiOff } from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import type { NetworkData, ConnectivityItem, RegionInfo } from "@/types"

function RegionCard({ region }: { region: RegionInfo }) {
  if (!region.ok) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          无法获取公网 IP 信息
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Globe className="h-4 w-4" />
          公网信息
          <Badge variant="outline">{region.source}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-2 sm:grid-cols-2">
          {[
            ["IP", region.ip],
            ["国家", region.country],
            ["地区", region.region],
            ["城市", region.city],
            ["时区", region.timezone],
            ["运营商", region.org],
            ["延迟", region.latency_ms ? `${region.latency_ms}ms` : undefined],
          ]
            .filter(([, v]) => v)
            .map(([k, v]) => (
              <div key={k} className="flex items-center justify-between rounded-md border p-2">
                <dt className="text-xs text-muted-foreground">{k}</dt>
                <dd className="font-mono text-xs">{v}</dd>
              </div>
            ))}
        </dl>
      </CardContent>
    </Card>
  )
}

function ConnectivityCard({ items }: { items: ConnectivityItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Wifi className="h-4 w-4" />
          连通性检测
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-2">
          {items.map((item) => (
            <div
              key={item.name}
              className="flex items-center justify-between rounded-md border p-3"
            >
              <div className="flex items-center gap-2">
                {item.ok ? (
                  <Wifi className="h-4 w-4 text-green-600" />
                ) : (
                  <WifiOff className="h-4 w-4 text-destructive" />
                )}
                <span className="font-medium">{item.name}</span>
              </div>
              <div className="flex items-center gap-2">
                {item.latency_ms !== undefined && (
                  <span className="font-mono text-xs text-muted-foreground">
                    {item.latency_ms}ms
                  </span>
                )}
                {item.status !== undefined && (
                  <Badge variant={item.ok ? "default" : "destructive"}>
                    {item.status}
                  </Badge>
                )}
                {item.error && (
                  <Badge variant="destructive" className="max-w-[200px] truncate">
                    {item.error}
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

export default function NetworkPage() {
  const { data, loading, error, refresh } = usePolling(() => api.network(), 0)

  const net: NetworkData | null = data

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">网络检测</h1>
            <p className="text-sm text-muted-foreground">正在探测网络环境...</p>
          </div>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">正在检测公网 IP 和连通性，请稍候（约需 5-15 秒）</p>
            <Button size="sm" variant="outline" onClick={refresh}>
              <RefreshCw className="mr-1.5 h-4 w-4" />
              重新检测
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">网络检测</h1>
            <p className="text-sm text-muted-foreground">公网信息与服务连通性</p>
          </div>
          <Button size="sm" variant="outline" onClick={refresh}>
            <RefreshCw className="mr-1.5 h-4 w-4" />
            重新检测
          </Button>
        </div>
        <p className="py-12 text-center text-muted-foreground">检测失败: {error}</p>
      </div>
    )
  }

  if (!net) return null

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">网络检测</h1>
          <p className="text-sm text-muted-foreground">公网信息与服务连通性</p>
        </div>
        <Button size="sm" variant="outline" onClick={refresh} disabled={loading}>
          <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          重新检测
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RegionCard region={net.region} />
        <ConnectivityCard items={net.connectivity} />
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span>
              代理: {net.proxy_enabled ? "已启用" : "未启用"}
            </span>
            {net.proxy_enabled && net.proxy_display && (
              <span className="font-mono text-xs">{net.proxy_display}</span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
