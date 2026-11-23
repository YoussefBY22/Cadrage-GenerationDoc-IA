"use client";

import { useParams } from "next/navigation";
import DecisionsView from "@/components/DecisionsView";
import Shell from "@/components/Shell";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <DecisionsView dossierId={id} />
    </Shell>
  );
}
