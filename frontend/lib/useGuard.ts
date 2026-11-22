"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { ApiError } from "./api";
import { t } from "./i18n";

/** Renvoie un gestionnaire d'erreur : 401 -> page de connexion, sinon message lisible. */
export function useGuard() {
  const router = useRouter();
  return useCallback(
    (err: unknown): string => {
      if (err instanceof ApiError) {
        if (err.status === 401) router.push("/login");
        return err.message;
      }
      return t.common.error;
    },
    [router],
  );
}
