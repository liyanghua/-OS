import { Suspense } from "react";
import { ReviewCaptureView } from "@/components/review/review-capture-view";

export default function ReviewCapturePage() {
  return (
    <Suspense
      fallback={
        <p className="p-4 text-sm text-[var(--muted)]">加载复盘沉淀台…</p>
      }
    >
      <ReviewCaptureView />
    </Suspense>
  );
}
