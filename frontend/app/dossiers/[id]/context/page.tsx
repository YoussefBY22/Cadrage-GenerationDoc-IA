"use client";

import { useParams } from "next/navigation";
import ContextView from "@/components/ContextView";
import Shell from "@/components/Shell";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <ContextView dossierId={id} />
    </Shell>
  );
}
