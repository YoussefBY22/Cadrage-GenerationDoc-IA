"use client";

import { useParams } from "next/navigation";
import RoadmapView from "@/components/editor/RoadmapView";
import Shell from "@/components/Shell";

export default function RoadmapPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <RoadmapView id={id} />
    </Shell>
  );
}
