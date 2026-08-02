import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/hooks/use-auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { LogoMark } from "@/components/shared/LogoMark"
import { LoadingSpinner } from "@/components/shared/LoadingSpinner"

export default function LoginPage() {
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!password.trim()) return
      setLoading(true)
      setError(null)
      const err = await login(password.trim())
      if (err) {
        setError(err)
        setLoading(false)
      } else {
        navigate("/admin/dashboard", { replace: true })
      }
    },
    [password, login, navigate],
  )

  return (
    <div className="login-page-shell flex min-h-screen items-center justify-center bg-background p-4">
      <div className="flex w-full max-w-sm flex-col items-center gap-8">
        <div className="login-brand flex flex-col items-center gap-3">
          <LogoMark className="h-12 w-12" />
          <div className="text-center">
            <h1 className="text-xl font-semibold tracking-tight">
              Freebuff2API
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">管理控制台</p>
          </div>
        </div>

        <Card className="login-card w-full">
          <CardContent>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <label
                  htmlFor="password"
                  className="text-sm font-medium text-foreground"
                >
                  管理密钥
                </label>
                <Input
                  id="password"
                  type="password"
                  placeholder="输入 FREEBUFF_ADMIN_KEY"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                  autoComplete="current-password"
                />
              </div>

              {error && (
                <div className="login-error rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {error}
                </div>
              )}

              <Button type="submit" className="w-full" disabled={loading}>
                {loading && <LoadingSpinner size={14} className="mr-2" />}
                {loading ? "登录中..." : "登录"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
