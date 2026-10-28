import { CircleCheck, CircleHelp, CircleOff, TriangleAlert } from "lucide-react";

import type { ConditionResult, ModelInfo } from "@/lib/api/types";
import { percent } from "@/lib/utils";

import { SeverityMeter } from "./SeverityMeter";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "./ui/primitives";

function headline(result: ConditionResult) {
  if (!result.model_available) return { text: "Model not available yet", tone: "neutral" as const, Icon: CircleOff };
  if (result.uncertain) return { text: "Borderline: specialist review", tone: "medium" as const, Icon: CircleHelp };
  if (result.positive) return { text: "Signs detected: refer", tone: "high" as const, Icon: TriangleAlert };
  return { text: "No signs detected", tone: "low" as const, Icon: CircleCheck };
}

/** How far to trust this result: the model's measured test figures, shown only if it is the same model version. */
function ModelReliability({ result, model }: { result: ConditionResult; model: ModelInfo }) {
  if (model.version !== result.model_version) return null;
  const m = model.metrics;
  if (!m) return <p className="text-xs text-muted-foreground">Model performance: {model.metrics_status}.</p>;
  const falseAlarms = Math.round((1 - m.precision) * 10);
  return (
    <div data-testid={`reliability-${result.condition}`} className="rounded-md bg-muted/60 p-2 text-xs text-muted-foreground">
      <p>
        <strong className="text-foreground">How reliable is this model?</strong> When measured, it found {percent(m.sensitivity)} of
        cases (sensitivity), cleared {percent(m.specificity)} of healthy eyes (specificity), and{" "}
        {falseAlarms > 0 ? `about ${falseAlarms} in 10 of its positive flags were false alarms` : "almost none of its positive flags were false alarms"}{" "}
        (precision {percent(m.precision)}).
      </p>
      <p className="mt-1">{model.metrics_status}.</p>
    </div>
  );
}

/** One condition's outcome. Unavailable models are shown explicitly, never as a negative result. */
export function ScreeningResultCard({ result, model }: { result: ConditionResult; model?: ModelInfo }) {
  const { text, tone, Icon } = headline(result);
  return (
    <Card data-testid={`result-${result.condition}`}>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <CardTitle>{result.display_name || result.condition}</CardTitle>
          {result.model_version && <span className="text-[11px] text-muted-foreground">model {result.model_version}</span>}
        </div>
        <Badge tone={tone} className="w-fit"><Icon aria-hidden className="h-3.5 w-3.5" />{text}</Badge>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {result.model_available && result.probability !== null && result.threshold !== null ? (
          <>
            {result.severity_band !== null ? (
              <SeverityMeter band={result.severity_band} />
            ) : (
              <p className="text-xs text-muted-foreground">
                Binary result only: the data this model was trained on has no severity grades, so no severity band is given.
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Model score {percent(result.probability)} (referral threshold {percent(result.threshold)}). The score is how
              strongly the model leans towards signs of disease; it is not a probability that the patient has the disease.
            </p>
          </>
        ) : (
          <>
            <SeverityMeter band={null} />
            <p className="text-sm text-muted-foreground">
              No trained model is installed for this condition, so no result is given. Do not treat this as a normal result.
            </p>
          </>
        )}
        <p className="text-sm font-medium">{result.recommendation}</p>
        {result.model_available && model && <ModelReliability result={result} model={model} />}
      </CardContent>
    </Card>
  );
}
