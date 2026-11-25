"use client";

import { useParams } from "next/navigation";
import RecommendationsView from "@/components/RecommendationsView";
import Shell from "@/components/Shell";

export default function RecommendationsPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <RecommendationsView dossierId={id} />
    </Shell>
  );
}
