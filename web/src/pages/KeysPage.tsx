import { useState, useCallback } from "react"
import { api } from "@/lib/api-client"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { CopyButton } from "@/components/shared/CopyButton"
import { Plus, Trash2, X, Check, ToggleLeft, ToggleRight } from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import type { ApiKeysData, ApiKeyItem } from "@/types"

export default function KeysPage() {
  const { data, loading, refresh } = usePolling(() => api.getKeys(), 30000)
  const [adding, setAdding] = useState(false)
  const [newName, setNewName] = useState("")
  const [newKey, setNewKey] = useState("")
  const [busy, setBusy] = useState(false)

  const keysData: ApiKeysData | null = data

  const handleCreate = useCallback(async () => {
    if (!newName.trim() || !newKey.trim()) return
    setBusy(true)
    try {
      await api.createKey(newName.trim(), newKey.trim())
      setNewName("")
      setNewKey("")
      setAdding(false)
      refresh()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "创建失败"
      alert(msg)
    } finally {
      setBusy(false)
    }
  }, [newName, newKey, refresh])

  const handleDelete = useCallback(async (name: string) => {
    if (!confirm(`确定删除 API Key「${name}」？`)) return
    setBusy(true)
    try {
      await api.deleteKey(name)
      refresh()
    } catch {
      alert("删除失败")
    } finally {
      setBusy(false)
    }
  }, [refresh])

  const handleToggle = useCallback(async (name: string) => {
    setBusy(true)
    try {
      await api.toggleKey(name)
      refresh()
    } catch {
      alert("切换失败")
    } finally {
      setBusy(false)
    }
  }, [refresh])

  if (loading && !keysData) {
    return <div className="py-20 text-center text-muted-foreground">加载中...</div>
  }

  const items: ApiKeyItem[] = keysData?.items || []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API Key 管理</h1>
          <p className="text-sm text-muted-foreground">
            共 {keysData?.count || 0} 个 Key，{keysData?.active_count || 0} 个启用
          </p>
        </div>
        <Button size="sm" onClick={() => setAdding(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          创建 Key
        </Button>
      </div>

      {adding && (
        <Card>
          <CardContent className="flex flex-col gap-3 p-4">
            <div className="flex gap-3">
              <Input
                placeholder="名称（如 production、dev）"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                autoFocus
              />
              <Input
                placeholder="密钥值（至少8位）"
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                className="font-mono"
              />
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} disabled={busy}>
                <Check className="mr-1 h-4 w-4" />
                创建
              </Button>
              <Button size="sm" variant="ghost" onClick={() => { setAdding(false); setNewName(""); setNewKey("") }}>
                <X className="mr-1 h-4 w-4" />
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {items.length === 0 && !adding && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <p className="text-muted-foreground">暂无 API Key</p>
            <Button onClick={() => setAdding(true)}>
              <Plus className="mr-1.5 h-4 w-4" />
              创建第一个 Key
            </Button>
          </CardContent>
        </Card>
      )}

      {items.map((k) => (
        <Card key={k.name}>
          <CardContent className="flex items-center gap-4 p-4">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{k.name}</span>
                <Badge variant={k.enabled ? "default" : "secondary"}>
                  {k.enabled ? "启用" : "禁用"}
                </Badge>
              </div>
              <div className="mt-1 flex items-center gap-2">
                <code className="font-mono text-sm text-muted-foreground">
                  {k.key}
                </code>
                <CopyButton text={k.key} />
              </div>
              <p className="mt-1 text-xs text-muted-foreground/70">
                模型白名单: {k.allowed_models?.join(", ") || "*"}
              </p>
            </div>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleToggle(k.name)}
                title={k.enabled ? "禁用" : "启用"}
                disabled={busy}
              >
                {k.enabled ? (
                  <ToggleRight className="h-5 w-5 text-primary" />
                ) : (
                  <ToggleLeft className="h-5 w-5 text-muted-foreground" />
                )}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => handleDelete(k.name)}
                title="删除"
                disabled={busy}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
