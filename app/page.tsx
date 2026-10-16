import { Suspense } from "react";
import { Workspace } from "@/app/_components/workspace";

export default function Page() {
  return (
    <Suspense>
      <Workspace />
    </Suspense>
  );
}
