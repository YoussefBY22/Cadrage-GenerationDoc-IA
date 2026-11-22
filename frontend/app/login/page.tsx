"use client";

import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Footer } from "@/components/Shell";
import { Alert, LangSwitch, Logo } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await api.login(email, password);
      router.push("/dossiers");
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t.login.bad : t.common.error);
    }
  };

  return (
    <div className="auth">
      <section className="auth-art">
        <Logo />
        <h2>{t.login.tagline}</h2>
        <span />
      </section>
      <main className="auth-form">
        <div className="auth-top">
          <LangSwitch />
        </div>
        <form onSubmit={submit}>
          <h1>{t.login.title}</h1>
          <label className="field">
            {t.login.email}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
          </label>
          <label className="field">
            {t.login.password}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {error && <Alert>{error}</Alert>}
          <button type="submit" className="btn btn-primary" style={{ justifyContent: "center", padding: "10px 14px" }}>
            {t.login.submit}
            <ArrowRight size={16} />
          </button>
        </form>
        <Footer />
      </main>
    </div>
  );
}
