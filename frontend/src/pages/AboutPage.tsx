import { CircleCheck, CircleOff } from "lucide-react";

import { PageHeader } from "@/components/AppShell";
import { Disclaimer, ErrorState, ListSkeleton } from "@/components/feedback";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "@/components/ui/primitives";
import { useModels } from "@/hooks/queries";
import type { ModelInfo } from "@/lib/api/types";
import { percent } from "@/lib/utils";

function Metrics({ model }: { model: ModelInfo }) {
  if (!model.metrics) {
    return <p className="text-sm"><strong>Performance:</strong> {model.metrics_status}. No accuracy figures are shown until they are measured on held-out images.</p>;
  }
  const m = model.metrics;
  const ci = m.confidence_intervals ?? {};
  const row = (label: string, key: "sensitivity" | "specificity" | "precision") => (
    <tr className="border-t"><td className="py-1">{label}</td><td className="py-1 text-right tabular-nums">{percent(m[key], 1)}</td>
      <td className="py-1 text-right text-xs text-muted-foreground tabular-nums">{ci[key] ? `${percent(ci[key].low, 1)} to ${percent(ci[key].high, 1)}` : "-"}</td></tr>
  );
  return (
    <div className="text-sm">
      <table className="w-full text-left">
        <thead><tr><th className="py-1">Metric ({m.evaluation_set ?? "test set"}, {m.test_images.toLocaleString()} images)</th><th className="py-1 text-right">Value</th><th className="py-1 text-right">95% interval</th></tr></thead>
        <tbody>
          {row("Sensitivity", "sensitivity")}
          {row("Specificity", "specificity")}
          {row("Precision", "precision")}
          <tr className="border-t"><td className="py-1">Accuracy</td><td className="py-1 text-right tabular-nums">{percent(m.accuracy, 1)}</td><td /></tr>
          <tr className="border-t"><td className="py-1">AUC</td><td className="py-1 text-right tabular-nums">{m.auc === null ? "not computed" : m.auc.toFixed(3)}</td><td /></tr>
        </tbody>
      </table>
      <p className="mt-2 text-xs text-muted-foreground">Status: {model.metrics_status}.</p>
    </div>
  );
}

export function AboutPage() {
  const models = useModels();
  return (
    <>
      <PageHeader title="About the models" description="What each model is, how it was built and what it cannot do." />
      <Disclaimer />
      <div className="mt-3 flex flex-col gap-3">
        {models.isPending && <ListSkeleton rows={3} />}
        {models.isError && <ErrorState error={models.error} onRetry={() => void models.refetch()} />}
        {models.data?.map((model) => (
          <Card key={model.condition}>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle>{model.display_name}</CardTitle>
                {model.available
                  ? <Badge tone="low"><CircleCheck aria-hidden className="h-3.5 w-3.5" />Available</Badge>
                  : <Badge><CircleOff aria-hidden className="h-3.5 w-3.5" />Model not available yet</Badge>}
              </div>
              {model.version && <p className="text-xs text-muted-foreground">Version {model.version}</p>}
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm">
              {!model.available && <p className="text-muted-foreground">{model.status_reason}</p>}
              {model.available && (
                <>
                  <Metrics model={model} />
                  <dl className="grid gap-2">
                    {model.architecture && <div><dt className="font-medium">Architecture</dt><dd className="text-muted-foreground">{model.architecture}</dd></div>}
                    {model.training?.dataset && <div><dt className="font-medium">Training data</dt><dd className="text-muted-foreground">{model.training.dataset}</dd></div>}
                    {model.training?.run && <div><dt className="font-medium">Training run</dt><dd className="text-muted-foreground">{model.training.run}</dd></div>}
                    {model.threshold !== null && <div><dt className="font-medium">Decision threshold</dt>
                      <dd className="text-muted-foreground">{model.threshold.toFixed(3)} ({model.threshold_source}); borderline zone ±{model.uncertainty_margin}</dd></div>}
                  </dl>
                  <div>
                    <p className="font-medium">Limitations</p>
                    <ul className="list-disc pl-5 text-muted-foreground">{model.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
