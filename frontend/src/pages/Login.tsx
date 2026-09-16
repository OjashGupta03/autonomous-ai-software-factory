import { useState } from "react";
import { Compass } from "lucide-react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/common/Button";

export function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login, register, isAuthenticating, error, user } = useAuthStore();

  if (user) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (mode === "login") {
      await login(email, password).catch(() => {});
    } else {
      await register(email, password).catch(() => {});
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 justify-center mb-8">
          <Compass size={28} className="text-brass" strokeWidth={2} />
          <span className="font-display text-xl font-semibold text-text-primary">Daedalus</span>
        </div>

        <form onSubmit={handleSubmit} className="bg-surface border border-border rounded-md p-6 flex flex-col gap-4">
          <h1 className="font-display text-lg font-medium text-text-primary">
            {mode === "login" ? "Sign in" : "Create an account"}
          </h1>

          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-text-secondary">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="bg-base border border-border rounded px-3 py-2 text-text-primary focus:border-signal outline-none"
              autoComplete="email"
            />
          </label>

          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-text-secondary">Password</span>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-base border border-border rounded px-3 py-2 text-text-primary focus:border-signal outline-none"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </label>

          {error && <p className="text-status-failure text-sm">{error}</p>}

          <Button type="submit" variant="primary" disabled={isAuthenticating} className="justify-center mt-2">
            {isAuthenticating ? "Please wait..." : mode === "login" ? "Sign in" : "Create account"}
          </Button>

          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            className="text-text-tertiary hover:text-text-secondary text-sm text-center"
          >
            {mode === "login" ? "Need an account? Register" : "Already have an account? Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
