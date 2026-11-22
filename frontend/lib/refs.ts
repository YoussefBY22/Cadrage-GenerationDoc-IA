/** Références des livrables d'un dossier (le serveur n'a pas encore de liste : voir docs/lots/UI.md). */
export interface DossierRefs {
  roadmap?: string;
  tor?: string;
  initiative?: string;
}

const key = (dossierId: string) => `cadrage.refs.${dossierId}`;

export function getRefs(dossierId: string): DossierRefs {
  try {
    return JSON.parse(window.localStorage.getItem(key(dossierId)) ?? "{}") as DossierRefs;
  } catch {
    return {};
  }
}

export function setRefs(dossierId: string, patch: DossierRefs): DossierRefs {
  const next = { ...getRefs(dossierId), ...patch };
  try {
    window.localStorage.setItem(key(dossierId), JSON.stringify(next));
  } catch {
    /* stockage indisponible */
  }
  return next;
}

const LAST = "cadrage.lastDossier";

export function setLastDossier(id: string): void {
  try {
    window.localStorage.setItem(LAST, id);
  } catch {
    /* ignoré */
  }
}

export function getLastDossier(): string | null {
  try {
    return window.localStorage.getItem(LAST);
  } catch {
    return null;
  }
}
