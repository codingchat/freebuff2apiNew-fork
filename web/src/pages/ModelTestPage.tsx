import { useState, useCallback } from "react"
import { api } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Terminal, Play, Loader2 } from "lucide-react"
import { usePolling } from "@/hooks/use-polling"
import type { ModelsResponse, ChatTestResult } from "@/types"

export default function ModelTestPage() {
  const { data: modelsData } = usePolling(() => api.models(), 60000)
  const [selectedModel, setSelectedModel] = useState("")
  const [prompt, setPrompt] = useState("Hello, say hi in one sentence.")
  const [result, setResult] = useState<ChatTestResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const models: ModelsResponse | null = modelsData

  const handleTest = useCallback(async () => {
    if (!selectedModel || !prompt.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.chatTest(selectedModel, prompt.trim())
      setResult(res)
      if (!res.ok) {
        setError(res.info || "测试失败")
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "请求失败"
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [selectedModel, prompt])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">模型调用测试</h1>
        <p className="text-sm text-muted-foreground">选择模型发起一次非流式调用测试</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Terminal className="h-4 w-4" />
            测试配置
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex gap-3">
            <Select value={selectedModel} onValueChange={(v) => setSelectedModel(v ?? "")}>
              <SelectTrigger className="w-64">
                <SelectValue placeholder="选择模型" />
              </SelectTrigger>
              <SelectContent>
                {models?.data?.map((m) => (
                  <SelectItem key={m.id} value={m.id}>
                    {m.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              onClick={handleTest}
              disabled={loading || !selectedModel || !prompt.trim()}
            >
              {loading ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-1.5 h-4 w-4" />
              )}
              发送测试
            </Button>
          </div>
          <Input
            placeholder="输入测试 Prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        </CardContent>
      </Card>

      {error && (
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {result && result.ok && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">响应结果</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-md bg-muted p-4 font-mono text-xs leading-relaxed">
              {typeof result.response === "string"
                ? result.response
                : JSON.stringify(result.response, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
