import { useState, useCallback } from "react"
import { api } from "@/lib/api-client"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { CopyButton } from "@/components/shared/CopyButton"
import {
  Plus, Pencil, Trash2, Check, X, ExternalLink, ShieldCheck, Info,
  RefreshCw,
} from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import type { ConfigPayload, TokenRow, TokenVerifyResult } from "@/types"

export default function TokenPage() {
  const { data, loading, refresh } = usePolling(() => api.config(), 30000)
  const [adding, setAdding] = useState(false)
  const [newToken, setNewToken] = useState("")
  const [editingIdx, setEditingIdx] = useState<number | null>(null)
  const [editToken, setEditToken] = useState("")
  const [verifying, setVerifying] = useState<number | null>(null)
  const [verifyResult, setVerifyResult] = useState<{ idx: number; result: TokenVerifyResult } | null>(null)
  const [busy, setBusy] = useState(false)

  const config: ConfigPayload | null = data

  const handleAdd = useCallback(async () => {
    if (!newToken.trim()) return
    setBusy(true)
    try {
      await api.addToken(newToken.trim())
      setNewToken("")
      setAdding(false)
      refresh()
    } catch { alert("添加失败") }
    finally { setBusy(false) }
  }, [newToken, refresh])

  const handleUpdate = useCallback(async (index: number) => {
    if (!editToken.trim()) return
    setBusy(true)
    try {
      await api.updateToken(index, editToken.trim())
      setEditingIdx(null)
      refresh()
    } catch { alert("更新失败") }
    finally { setBusy(false) }
  }, [editToken, refresh])

  const handleDelete = useCallback(async (index: number) => {
    if (!confirm(`确定删除 Token #${index}？`)) return
    setBusy(true)
    try { await api.deleteToken(index); refresh() }
    catch { alert("删除失败") }
    finally { setBusy(false) }
  }, [refresh])

  const handleVerify = useCallback(async (index: number) => {
    setVerifying(index)
    setVerifyResult(null)
    try {
      const detail = await api.getToken(index)
      const result = await api.verifyToken(detail.token)
      setVerifyResult({ idx: index, result })
    } catch {
      setVerifyResult({ idx: index, result: { ok: false, info: "验证请求失败" } })
    } finally { setVerifying(null) }
  }, [])

  if (loading && !config) {
    return <div className="py-20 text-center text-muted-foreground">加载中...</div>
  }

  const tokens: TokenRow[] = config?.tokens || []

  return (
    <div className="mx-auto w-full max-w-[960px] space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Token 管理</h1>
          <p className="text-sm text-muted-foreground">
            管理 Freebuff 上游 Token（共 {tokens.length} 个）
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => window.open("https://freebuff.071129.xyz/", "_blank", "noopener")}>
            <ExternalLink className="mr-1.5 h-4 w-4" />获取 Token
          </Button>
          <Button size="sm" onClick={() => { setAdding(true); window.open("https://freebuff.071129.xyz/", "_blank", "noopener") }}>
            <Plus className="mr-1.5 h-4 w-4" />添加 Token
          </Button>
        </div>
      </div>

      {adding && (
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <Alert>
              <Info className="h-4 w-4" />
              <AlertDescription>
                已打开 Token 获取页面。完成认证后复制 token，回到这里粘贴并保存。也可以手动打开：
                <a href="https://freebuff.071129.xyz/" target="_blank" rel="noopener" className="underline ml-1">https://freebuff.071129.xyz/</a>
              </AlertDescription>
            </Alert>
            <div className="flex items-center gap-3">
              <Input placeholder="粘贴 Freebuff Token" value={newToken} onChange={(e) => setNewToken(e.target.value)} autoFocus className="flex-1 font-mono text-sm" />
              <Button size="sm" onClick={handleAdd} disabled={busy}><Check className="mr-1 h-4 w-4" />保存</Button>
              <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setNewToken("") }}><X className="mr-1 h-4 w-4" />取消</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {tokens.length === 0 && !adding && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <ShieldCheck className="h-12 w-12 text-muted-foreground/30" />
            <p className="text-muted-foreground">暂无 Token，请添加至少一个</p>
            <Button onClick={() => { setAdding(true); window.open("https://freebuff.071129.xyz/", "_blank", "noopener") }}>
              <Plus className="mr-1.5 h-4 w-4" />添加第一个 Token
            </Button>
          </CardContent>
        </Card>
      )}

      {tokens.map((t) => (
        <Card key={t.index} className="border-border/60 shadow-sm">
          <CardContent className="flex items-center gap-4 p-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">#{t.index}</div>
            <div className="min-w-0 flex-1">
              {editingIdx === t.index ? (
                <div className="flex items-center gap-2">
                  <Input value={editToken} onChange={(e) => setEditToken(e.target.value)} autoFocus className="font-mono text-sm" />
                  <Button size="sm" onClick={() => handleUpdate(t.index)} disabled={busy}><Check className="h-4 w-4" /></Button>
                  <Button size="sm" variant="ghost" onClick={() => setEditingIdx(null)}><X className="h-4 w-4" /></Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <code className="truncate font-mono text-sm text-muted-foreground">{t.masked}</code>
                  <CopyButton text={t.masked} />
                  {verifyResult?.idx === t.index && (
                    <Badge variant={verifyResult.result.ok ? "default" : "destructive"} className="text-[10px]">
                      {verifyResult.result.ok ? "有效" : "无效"}
                    </Badge>
                  )}
                </div>
              )}
              <p className="mt-1 text-xs text-muted-foreground/70">长度: {t.length} | 前缀: {t.prefix}</p>
              {verifyResult?.idx === t.index && (
                <p className={`mt-0.5 text-xs ${verifyResult.result.ok ? "text-green-600" : "text-destructive"}`}>{verifyResult.result.info}</p>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" onClick={() => handleVerify(t.index)} disabled={verifying === t.index} title="验证 Token">
                {verifying === t.index ? <RefreshCw className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setEditingIdx(t.index); setEditToken("") }} title="编辑"><Pencil className="h-4 w-4" /></Button>
              <Button size="sm" variant="ghost" onClick={() => handleDelete(t.index)} title="删除"><Trash2 className="h-4 w-4 text-destructive" /></Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
