"use client";

import { useParams } from "next/navigation";
import ProjectsView from "@/components/ProjectsView";
import Shell from "@/components/Shell";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return (
    <Shell>
      <ProjectsView dossierId={id} />
    </Shell>
  );
}
