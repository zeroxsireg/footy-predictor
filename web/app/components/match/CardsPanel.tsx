import { ProbList } from "@/app/components/ui/ProbBar";
import { Label } from "@/app/components/ui/Label";
import { cardLines, rows, HOT } from "@/app/lib/markets";
import { dec } from "@/app/lib/format";
import { getDict } from "@/app/lib/i18n-server";
import type { Markets } from "@/app/lib/types";

export function CardsPanel({ cards }: { cards: NonNullable<Markets["cards"]> }) {
  const dict = getDict();
  return (
    <div>
      <div className="mb-4 flex items-baseline gap-3">
        <span className="hd text-4xl text-red">{dec(cards.expected)}</span>
        <Label>{dict.match.sections.cardsExpected}</Label>
      </div>
      <ProbList items={rows(cards, cardLines(dict))} hotAt={HOT} />
    </div>
  );
}
