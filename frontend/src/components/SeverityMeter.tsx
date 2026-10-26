import { cn } from "@/lib/utils";

const BANDS = [
  { band: 1, label: "1", tone: "bg-risk-low" },
  { band: 2, label: "2", tone: "bg-risk-low" },
  { band: 3, label: "3", tone: "bg-risk-medium" },
  { band: 4, label: "4", tone: "bg-risk-high" },
  { band: 5, label: "5", tone: "bg-risk-high" },
] as const;

const BAND_TEXT: Record<number, string> = {
  1: "lower", 2: "lower", 3: "borderline", 4: "higher", 5: "higher",
};

/**
 * Five labelled segments for the *estimated* severity band. `band = null` renders an explicit
 * "unavailable" state rather than an empty or zero meter, so a missing model is never mistaken
 * for a low-risk result.
 */
export function SeverityMeter({ band }: { band: number | null }) {
  if (band === null) {
    return (
      <div role="img" aria-label="Estimated severity band: unavailable" className="flex flex-col gap-1">
        <div className="flex gap-1">
          {BANDS.map((b) => <span key={b.band} className="h-3 flex-1 rounded-sm border border-dashed border-input" />)}
        </div>
        <p className="text-xs text-muted-foreground">Estimated severity band: unavailable</p>
      </div>
    );
  }
  return (
    <div role="img" aria-label={`Estimated severity band ${band} of 5 (${BAND_TEXT[band]})`} className="flex flex-col gap-1">
      <div className="flex gap-1">
        {BANDS.map((b) => (
          <span key={b.band} className={cn("flex h-5 flex-1 items-center justify-center rounded-sm text-[10px] font-semibold",
            b.band === band ? cn(b.tone, "text-white ring-2 ring-offset-1 ring-foreground/40") : "bg-muted text-muted-foreground")}>
            {b.label}
          </span>
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>Lower</span><span>Borderline</span><span>Higher</span>
      </div>
      <p className="text-xs">
        Estimated severity band <strong>{band}</strong> of 5. An estimate from the model score, not a clinical grade.
      </p>
    </div>
  );
}
