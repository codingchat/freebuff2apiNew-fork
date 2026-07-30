import { NavLink, Outlet, useNavigate } from "react-router-dom"
import { useAuth } from "@/hooks/use-auth"
import { useDashboardTheme } from "@/components/theme/theme-context"
import {
  LayoutDashboard,
  KeyRound,
  ShieldCheck,
  ScrollText,
  Globe,
  Server,
  Terminal,
  Settings,
  FileText,
  LogOut,
  Sun,
  Moon,
  Monitor,
} from "lucide-react"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { to: "/admin/dashboard", label: "概览", icon: LayoutDashboard },
  { to: "/admin/token", label: "Token 管理", icon: KeyRound },
  { to: "/admin/keys", label: "API Key", icon: ShieldCheck },
  { to: "/admin/logs", label: "运行日志", icon: ScrollText },
  { to: "/admin/requests", label: "请求记录", icon: FileText },
  { to: "/admin/env", label: "Env 查看", icon: Server },
  { to: "/admin/network", label: "网络检测", icon: Globe },
  { to: "/admin/model-test", label: "模型测试", icon: Terminal },
  { to: "/admin/settings", label: "设置", icon: Settings },
]

const themeIcons = {
  "porcelain-moss": Sun,
  "tungsten-dark": Moon,
  system: Monitor,
}

export default function AppLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const { mode, setMode, options } = useDashboardTheme()

  const handleLogout = async () => {
    await logout()
    navigate("/admin/login", { replace: true })
  }

  const cycleTheme = () => {
    const idx = options.findIndex((o) => o.mode === mode)
    const next = options[(idx + 1) % options.length]
    setMode(next.mode)
  }

  const ThemeIcon = themeIcons[mode] || Monitor

  return (
    <div className="admin-shell flex h-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-sidebar lg:flex">
        <div className="flex h-14 items-center gap-2 border-b border-sidebar-border px-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-logo-background">
            <div className="h-3 w-3 rounded-full bg-logo-start" />
          </div>
          <span className="text-sm font-semibold text-sidebar-foreground">
            Freebuff2API
          </span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-3">
          <div className="flex flex-col gap-0.5">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                    isActive
                      ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                      : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </div>
        </nav>

        <div className="border-t border-sidebar-border p-3">
          <div className="flex items-center gap-2">
            <button
              onClick={cycleTheme}
              className="flex h-8 w-8 items-center justify-center rounded-md text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
              title="切换主题"
            >
              <ThemeIcon className="h-4 w-4" />
            </button>
            <button
              onClick={handleLogout}
              className="flex flex-1 items-center gap-2 rounded-md px-3 py-2 text-sm text-sidebar-foreground/60 hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"
            >
              <LogOut className="h-4 w-4" />
              退出登录
            </button>
          </div>
        </div>
      </aside>

      {/* Mobile header */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-4 lg:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-logo-background">
              <div className="h-2.5 w-2.5 rounded-full bg-logo-start" />
            </div>
            <span className="text-sm font-semibold">Freebuff2API</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={cycleTheme}
              className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
            >
              <ThemeIcon className="h-4 w-4" />
            </button>
            <button
              onClick={handleLogout}
              className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
