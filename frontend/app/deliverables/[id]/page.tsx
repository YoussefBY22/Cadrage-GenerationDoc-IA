"use client";

import { useParams } from "next/navigation";
import DeliverableView from "@/components/editor/DeliverableView";
import Shell from "@/components/Shell";

export default function DeliverablePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <DeliverableView id={id} />
    </Shell>
  );
}
