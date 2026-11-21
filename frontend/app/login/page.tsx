"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ApiError, api } from "@/lib/api";
import { t } from "@/lib/i18n/fr";

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
    <main>
      <h1>{t.login.title}</h1>
      <form onSubmit={submit} className="card">
        <p>
          <label>
            {t.login.email}
            <br />
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
        </p>
        <p>
          <label>
            {t.login.password}
            <br />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        </p>
        {error && <p role="alert">{error}</p>}
        <button type="submit">{t.login.submit}</button>
      </form>
    </main>
  );
}
