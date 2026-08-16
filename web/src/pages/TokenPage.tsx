import { useState, useCallback, useEffect } from "react"
import type { RotationModeData } from "@/types"
import { api } from "@/lib/api-client"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { CopyButton } from "@/components/shared/CopyButton"
import {
  Plus, Pencil, Trash2, Check, X, ExternalLink, ShieldCheck, Info,
  RefreshCw, Target, Activity, Ban,
} from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import { Skeleton } from "@/components/ui/skeleton"
import {
  CardSkeleton,
  TokenStatusSkeleton,
} from "@/components/shared/PageSkeletons"
import type { ConfigPayload, TokenRow, TokenVerifyResult, AccountStatus } from "@/types"

interface MergedAccount extends TokenRow {
  status: AccountStatus["status"]
  block_remaining: number
  failure_count: number
  is_current: boolean
  last_429: Record<string, unknown>
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline"

const STATUS_META: Record<AccountStatus["status"], { label: string; variant: BadgeVariant }> = {
  active: { label: "活跃", variant: "default" },
  blocked: { label: "限流中", variant: "destructive" },
  invalid: { label: "失效", variant: "secondary" },
  checking: { label: "验证中", variant: "outline" },
}

function formatSeconds(sec: number): string {
  const total = Math.max(0, Math.round(sec))
  const m = Math.floor(total / 60)
  const s = total % 60
  return m > 0 ? `${m}分${s}秒` : `${s}秒`
}

function RotationModeCard() {
  const [modeData, setModeData] = useState<RotationModeData | null>(null)
  const [switching, setSwitching] = useState(false)

  const fetchMode = useCallback(async () => {
    try { setModeData(await api.getRotationMode()) } catch {}
  }, [])

  useEffect(() => { fetchMode() }, [fetchMode])

  const switchMode = useCallback(async (mode: string) => {
    setSwitching(true)
    try { setModeData(await api.setRotationMode(mode)) } catch {}
    setSwitching(false)
  }, [])

  const options = modeData?.options ?? []
  const current = modeData?.mode ?? ""

  return (
    <Card className="border-border/60 shadow-sm">
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">账号轮换模式</span>
          {modeData?.premium_banned_until ? (
            <Badge variant="destructive" className="text-xs">
              premium 已停用 · {new Date(modeData.premium_banned_until * 1000).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })} 恢复
            </Badge>
          ) : null}
        </div>
        <div className="flex gap-2">
          {options.map((opt) => (
            <button
              key={opt.value}
              disabled={switching}
              onClick={() => switchMode(opt.value)}
              className={`flex-1 rounded-lg border px-3 py-2 text-center text-xs transition-colors ${
                current === opt.value
                  ? "border-primary/60 bg-primary/10 text-primary font-medium"
                  : "border-border/60 hover:border-muted-foreground/30 text-muted-foreground"
              }`}
              title={opt.desc}
            >
              {opt.label}
            </button>
          ))}
        </div>
        <p className="text-[11px] text-muted-foreground">
          {options.find((o) => o.value === current)?.desc || "选择轮换策略"}
        </p>
      </CardContent>
    </Card>
  )
}

export default function TokenPage() {
  const { data, loading, refresh } = usePolling(() => api.config(), 30000)
  const [adding, setAdding] = useState(false)
  const [newToken, setNewToken] = useState("")
  const [editingIdx, setEditingIdx] = useState<number | null>(null)
  const [editToken, setEditToken] = useState("")
  const [verifying, setVerifying] = useState<number | null>(null)
  const [verifyResult, setVerifyResult] = useState<{ idx: number; result: TokenVerifyResult } | null>(null)
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const [fetchedAt, setFetchedAt] = useState(() => Date.now())

  // 1s ticker for live cooldown countdown
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  // Reset the fetchedAt anchor whenever config data is refreshed
  const dataKey = JSON.stringify(data?.rotation?.accounts?.map((a) => a.block_remaining))
  useEffect(() => { setFetchedAt(Date.now()) }, [dataKey])

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

  const handleRotate = useCallback(async () => {
    setBusy(true)
    try { await api.rotateTokens(); refresh() }
    catch { alert("轮换失败") }
    finally { setBusy(false) }
  }, [refresh])

  const handleActivate = useCallback(async (index: number) => {
    setBusy(true)
    try { await api.activateToken(index); refresh() }
    catch { alert("切换失败") }
    finally { setBusy(false) }
  }, [refresh])

  const handleValidate = useCallback(async () => {
    setBusy(true)
    try { await api.validateTokens(); refresh() }
    catch { alert("验证失败") }
    finally { setBusy(false) }
  }, [refresh])

  if (loading && !config) {
    return (
      <div className="mx-auto w-full max-w-[960px] space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-7 w-36" />
            <Skeleton className="h-4 w-64" />
          </div>
          <div className="flex gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-9 w-24" />
            ))}
          </div>
        </div>
        <TokenStatusSkeleton />
        {Array.from({ length: 3 }).map((_, i) => (
          <CardSkeleton key={i} className="flex items-center gap-4 p-4">
            <Skeleton className="h-10 w-10 rounded-lg" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-3 w-32" />
            </div>
            <Skeleton className="h-6 w-14" />
          </CardSkeleton>
        ))}
      </div>
    )
  }

  const tokens: TokenRow[] = config?.tokens || []
  const rotation = config?.rotation || null
  const accounts: AccountStatus[] = rotation?.accounts || []

  const merged: MergedAccount[] = tokens.map((t) => {
    const acc = accounts.find((a) => a.index === t.index)
    return {
      ...t,
      status: acc?.status ?? "active",
      block_remaining: acc?.block_remaining ?? 0,
      failure_count: acc?.failure_count ?? 0,
      is_current: acc?.is_current ?? false,
      last_429: acc?.last_429 ?? {},
    }
  })

  const liveRemaining = (account: MergedAccount): number =>
    Math.max(0, account.block_remaining - (now - fetchedAt) / 1000)

  const has429 = Boolean(rotation?.last_429_time)

  return (
    <div className="mx-auto w-full max-w-[960px] space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Token 管理</h1>
          <p className="text-sm text-muted-foreground">
            管理 Freebuff 上游账号（共 {merged.length} 个）
            {rotation ? ` · 可用 ${rotation.available_count} 个 · 累计轮换 ${rotation.total_rotations} 次` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => window.open("https://freebuff.071129.xyz/", "_blank", "noopener")}>
            <ExternalLink className="mr-1.5 h-4 w-4" />获取 Token
          </Button>
          <Button variant="outline" size="sm" onClick={handleRotate} disabled={busy} title="手动轮换到下一个可用账号">
            <RefreshCw className="mr-1.5 h-4 w-4" />手动轮换
          </Button>
          <Button variant="outline" size="sm" onClick={handleValidate} disabled={busy} title="重新校验所有账号有效性">
            <Activity className="mr-1.5 h-4 w-4" />校验账号
          </Button>
          <Button size="sm" onClick={() => { setAdding(true); window.open("https://freebuff.071129.xyz/", "_blank", "noopener") }}>
            <Plus className="mr-1.5 h-4 w-4" />添加 Token
          </Button>
        </div>
      </div>

      <RotationModeCard />

      {rotation?.all_blocked && (
        <Alert variant="destructive">
          <Ban className="h-4 w-4" />
          <AlertTitle>全部账号限流</AlertTitle>
          <AlertDescription>
            所有账号当前都处于 429 限流冷却中，请求将等待最早解封的账号。请稍后再试或补充新 Token。
          </AlertDescription>
        </Alert>
      )}

      {has429 && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>最近 429 限流</AlertTitle>
          <AlertDescription>
            时间：{rotation!.last_429_time || "-"}
            {rotation!.last_429_account ? ` · 账号 #${rotation!.last_429_account}` : ""}
            {String(rotation!.last_429_info?.model || "") ? ` · 模型：${String(rotation!.last_429_info.model)}` : ""}
            {String(rotation!.last_429_info?.retry_after_str || "") ? ` · 冷却：${String(rotation!.last_429_info.retry_after_str)}` : ""}
            {String(rotation!.last_429_info?.reset_at_sha || "") ? ` · 恢复：${String(rotation!.last_429_info.reset_at_sha)}` : ""}
          </AlertDescription>
        </Alert>
      )}

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
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Input placeholder="粘贴 Freebuff Token" value={newToken} onChange={(e) => setNewToken(e.target.value)} autoFocus className="flex-1 font-mono text-sm" />
              <div className="flex shrink-0 gap-2">
                <Button size="sm" onClick={handleAdd} disabled={busy}><Check className="mr-1 h-4 w-4" />保存</Button>
                <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setNewToken("") }}><X className="mr-1 h-4 w-4" />取消</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {merged.length === 0 && !adding && (
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

      {merged.map((t) => {
        const meta = STATUS_META[t.status]
        const remaining = liveRemaining(t)
        const hasLast429 = Object.keys(t.last_429).length > 0
        return (
          <Card key={t.index} className={`border-border/60 shadow-sm ${t.is_current ? "ring-1 ring-primary/40" : ""}`}>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-sm font-bold text-primary">#{t.index}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {editingIdx === t.index ? (
                    <div className="flex items-center gap-2">
                      <Input value={editToken} onChange={(e) => setEditToken(e.target.value)} autoFocus className="font-mono text-sm" />
                      <Button size="sm" onClick={() => handleUpdate(t.index)} disabled={busy}><Check className="h-4 w-4" /></Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditingIdx(null)}><X className="h-4 w-4" /></Button>
                    </div>
                  ) : (
                    <>
                      <code className="truncate font-mono text-sm text-muted-foreground">{t.masked}</code>
                      <CopyButton text={t.masked} />
                    </>
                  )}
                  <Badge variant={meta.variant} className="text-[10px]">{meta.label}</Badge>
                  {t.is_current && (
                    <Badge className="text-[10px]"><Target className="mr-0.5 h-3 w-3" />当前</Badge>
                  )}
                  {t.status === "blocked" && remaining > 0 && (
                    <Badge variant="outline" className="text-[10px] text-destructive">
                      冷却 {formatSeconds(remaining)}
                    </Badge>
                  )}
                  {verifyResult?.idx === t.index && (
                    <Badge variant={verifyResult.result.ok ? "default" : "destructive"} className="text-[10px]">
                      {verifyResult.result.ok ? "有效" : "无效"}
                    </Badge>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground/70">
                  <span>长度: {t.length}</span>
                  <span>前缀: {t.prefix}</span>
                  {t.failure_count > 0 && t.status !== "invalid" && (
                    <span className="text-amber-600">失败 {t.failure_count}/3</span>
                  )}
                  {hasLast429 && (
                    <span className="text-destructive/80">
                      最近 429: {String(t.last_429.model || "-")}
                      {String(t.last_429.retry_after_str || "") ? ` · ${String(t.last_429.retry_after_str)}` : ""}
                    </span>
                  )}
                </div>
                {verifyResult?.idx === t.index && (
                  <p className={`mt-0.5 text-xs ${verifyResult.result.ok ? "text-green-600" : "text-destructive"}`}>{verifyResult.result.info}</p>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button size="sm" variant="ghost" onClick={() => handleActivate(t.index)} disabled={busy || t.is_current} title="设为当前账号">
                  <Target className="h-4 w-4" />
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleVerify(t.index)} disabled={verifying === t.index} title="验证 Token">
                  {verifying === t.index ? <RefreshCw className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => { setEditingIdx(t.index); setEditToken("") }} title="编辑"><Pencil className="h-4 w-4" /></Button>
                <Button size="sm" variant="ghost" onClick={() => handleDelete(t.index)} title="删除"><Trash2 className="h-4 w-4 text-destructive" /></Button>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
