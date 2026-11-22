// Lance l'API de démonstration pour les tests de bout en bout (port 8001, modèle « demo », base SQLite jetable).
// Variables : CADRAGE_PYTHON (interpréteur Python du backend, « python » par défaut), E2E_API_PORT.
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const backend = path.resolve(here, "..", "..", "backend");
const work = path.resolve(here, "..", ".e2e");
const python = process.env.CADRAGE_PYTHON || "python";
const port = process.env.E2E_API_PORT || "8001";
const front = process.env.E2E_FRONT_ORIGIN || "http://localhost:3001";

rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });

const env = {
  ...process.env,
  LLM_PROVIDER: "demo",
  AUTH_MODE: "token",
  STORAGE_URL: `sqlite+pysqlite:///${path.join(work, "app.db").replaceAll("\\", "/")}`,
  UPLOAD_DIR: path.join(work, "uploads"),
  DATABASE_URL: "",
  CORS_ORIGINS: `${front},${front.replace("localhost", "127.0.0.1")}`,
  CADRAGE_PASSWORD: "demo-parcours-2026",
};

const run = (args) => {
  const r = spawnSync(python, args, { cwd: backend, env, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
};

// corpus synthétique (documents réalistes, institution fictive « Agence nationale de l'eau de Valmont »)
run([
  "-c",
  `from pathlib import Path; from eval.corpus.generate import generate; generate(7, Path(r"${path.join(work, "corpus")}"))`,
]);
run(["scripts/create_user.py", "consultante@demo.local", "Camille Laurent", "consultant"]);
run(["scripts/create_user.py", "relecteur@demo.local", "Hugo Martin", "reviewer"]);

const api = spawn(python, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port, "--log-level", "warning"], {
  cwd: backend,
  env,
  stdio: "inherit",
});
const stop = () => api.kill();
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
api.on("exit", (code) => process.exit(code ?? 0));
