"use client";

import { useEffect, useState } from "react";
import { api } from "./api";
import type { Dossier } from "./api-types";

/** Dossier courant (pour le fil d'Ariane) ; null tant qu'il charge ou s'il est introuvable. */
export function useDossier(id: string | undefined): Dossier | null {
  const [d, setD] = useState<Dossier | null>(null);
  useEffect(() => {
    if (!id) return;
    let alive = true;
    api
      .getDossier(id)
      .then((x) => alive && setD(x))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [id]);
  return d;
}
