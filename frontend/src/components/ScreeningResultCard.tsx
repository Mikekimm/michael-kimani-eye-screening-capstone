import { CircleCheck, CircleHelp, CircleOff, TriangleAlert } from "lucide-react";

import type { ConditionResult } from "@/lib/api/types";
import { percent } from "@/lib/utils";

import { SeverityMeter } from "./SeverityMeter";
import { Badge, Card, CardContent, CardHeader, CardTitle } from "./ui/primitives";

function headline(result: ConditionResult) {
  if (!result.model_available) return { text: "Model not available yet", tone: "neutral" as const, Icon: CircleOff };
  if (result.uncertain) return { text: "Borderline: specialist review", tone: "medium" as const, Icon: CircleHelp };
  if (result.positive) return { text: "Signs detected: refer", tone: "high" as const, Icon: TriangleAlert };
  return { text: "No signs detected", tone: "low" as const, Icon: CircleCheck };
}

/** One condition's outcome. Unavailable models are shown explicitly, never as a negative result. */
export function ScreeningResultCard({ result }: { result: ConditionResult }) {
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
            <SeverityMeter band={result.severity_band} />
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
      </CardContent>
    </Card>
  );
}
