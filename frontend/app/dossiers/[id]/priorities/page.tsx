"use client";

import { useParams } from "next/navigation";
import PrioritiesView from "@/components/PrioritiesView";
import Shell from "@/components/Shell";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <PrioritiesView dossierId={id} />
    </Shell>
  );
}
