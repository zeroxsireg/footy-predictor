import { cx } from "@/app/lib/cx";
import { pct, pad2 } from "@/app/lib/format";
import { PLAYER_HOT } from "@/app/lib/markets";
import { getDict } from "@/app/lib/i18n-server";
import type { Markets } from "@/app/lib/types";

export function PlayerRiskTable({
  players,
  home,
  away,
}: {
  players: NonNullable<Markets["players_at_risk"]>;
  home: string;
  away: string;
}) {
  const t = getDict().match.playerTable;
  const head = [t.player, t.role, t.risk];

  return (
    <table className="w-full text-sm">
      <thead>
        <tr>
          {head.map((h, i) => (
            <th
              key={h}
              className={cx("lbl pb-2 font-normal text-dim", i === 2 && "text-right")}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {players.map((p, i) => (
          <tr key={p.name} className="border-t border-line">
            <td className="py-2">
              <span className="text-dim mr-1">{pad2(i + 1)}</span> {p.name}
              {p.team && (
                <span className="ml-2 inline-block border border-dim px-1.5 py-0.5 text-[0.6rem] leading-none tracking-[0.08em] text-dim align-middle uppercase font-mono">
                  <span className="sm:hidden">{p.team === "home" ? "H" : "A"}</span>
                  <span className="hidden sm:inline">{p.team === "home" ? home : away}</span>
                </span>
              )}
            </td>
            <td className="text-dim">{p.position}</td>
            <td className="py-2 text-right">
              <data value={p.prob} className={cx(p.prob >= PLAYER_HOT ? "text-red" : "text-fg")}>
                {pct(p.prob)}
              </data>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
