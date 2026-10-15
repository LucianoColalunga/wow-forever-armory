import { Skeleton } from "@/components/ui";

export default function Loading() {
  return (
    <div className="space-y-4">
      <div className="h-8 w-64 animate-pulse rounded bg-surface-2" aria-hidden="true" />
      <Skeleton rows={8} />
    </div>
  );
}
