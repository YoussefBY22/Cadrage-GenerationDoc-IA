import { t } from "@/lib/i18n";

/** Libellés de l'éditeur : même dictionnaire que le reste de l'interface (clé `ed`). */
export const m: (typeof t)["ed"] = new Proxy({} as (typeof t)["ed"], {
  get: (_target, prop) => (t.ed as unknown as Record<string | symbol, unknown>)[prop],
});
