import { useState, useCallback } from "react"
import { api } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ShieldCheck, Info, Check } from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import type { ConfigPayload } from "@/types"

export default function SettingsPage() {
  const { data, refresh } = usePolling(() => api.config(), 30000)
  const [adminKey, setAdminKey] = useState("")
  const [busy, setBusy] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const config: ConfigPayload | null = data

  const handleUpdate = useCallback(async () => {
    if (!adminKey.trim() || adminKey.trim().length < 8) {
      setError("密钥至少需要 8 个字符")
      return
    }
    setBusy(true)
    setError(null)
    setSuccess(false)
    try {
      await api.updateSecurity(adminKey.trim())
      setSuccess(true)
      setAdminKey("")
      refresh()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "修改失败"
      setError(msg)
    } finally {
      setBusy(false)
    }
  }, [adminKey, refresh])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="text-sm text-muted-foreground">修改管理员密钥等配置</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <ShieldCheck className="h-4 w-4" />
            修改管理员密钥
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription className="flex items-center gap-2">
              修改后需要重新登录。当前状态:
              {config?.using_default_admin_key ? (
                <Badge variant="destructive">使用默认密钥</Badge>
              ) : (
                <Badge>已自定义</Badge>
              )}
            </AlertDescription>
          </Alert>

          <div className="flex gap-3">
            <Input
              type="password"
              placeholder="新的管理员密钥（至少8位）"
              value={adminKey}
              onChange={(e) => setAdminKey(e.target.value)}
              className="max-w-md"
            />
            <Button onClick={handleUpdate} disabled={busy}>
              {busy ? "保存中..." : "保存"}
            </Button>
          </div>

          {success && (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <Check className="h-4 w-4" />
              修改成功，请重新登录
            </div>
          )}
          {error && (
            <p className="text-sm text-destructive">{error}</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
