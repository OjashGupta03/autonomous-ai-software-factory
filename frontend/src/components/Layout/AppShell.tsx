import { Link, useLocation } from "react-router-dom";
import { Compass, LayoutDashboard, LogOut } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const { user, logout } = useAuthStore();

  return (
    <div className="min-h-screen bg-base flex flex-col">
      <header className="h-14 border-b border-border bg-surface flex items-center px-4 gap-6 shrink-0">
        <Link to="/" className="flex items-center gap-2 font-display font-semibold text-text-primary tracking-tight">
          <Compass size={20} className="text-brass" strokeWidth={2} />
          <span>Daedalus</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <NavLink to="/" active={location.pathname === "/"}>
            <LayoutDashboard size={14} />
            Dashboard
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          {user && (
            <>
              <span className="text-text-tertiary text-sm font-mono">{user.email}</span>
              <button
                onClick={logout}
                className="text-text-secondary hover:text-text-primary p-1.5 rounded transition-colors"
                aria-label="Log out"
                title="Log out"
              >
                <LogOut size={16} />
              </button>
            </>
          )}
        </div>
      </header>
      <main className="flex-1 min-h-0">{children}</main>
    </div>
  );
}

function NavLink({ to, active, children }: { to: string; active: boolean; children: React.ReactNode }) {
  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 rounded transition-colors",
        active ? "bg-surface-hover text-text-primary" : "text-text-secondary hover:text-text-primary"
      )}
    >
      {children}
    </Link>
  );
}
