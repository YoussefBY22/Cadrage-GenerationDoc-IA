"use client";

import { useParams } from "next/navigation";
import FindingsView from "@/components/FindingsView";
import Shell from "@/components/Shell";

export default function FindingsPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <FindingsView dossierId={id} />
    </Shell>
  );
}
