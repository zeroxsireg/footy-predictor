import { Label } from "@/app/components/ui/Label";
import { getDict } from "@/app/lib/i18n-server";
import type { Match } from "@/app/lib/types";

/** Actual outcome — only for already-played matches (backtest/demo). */
export function ResultBlock({ result }: { result: NonNullable<Match["result"]> }) {
  return (
    <div className="border border-red p-4 text-center">
      <Label bracket tone="red">
        {getDict().match.sections.realResult}
      </Label>
      <p className="hd mt-2 text-5xl text-red">
        {result.home_goals}–{result.away_goals}
      </p>
    </div>
  );
}
