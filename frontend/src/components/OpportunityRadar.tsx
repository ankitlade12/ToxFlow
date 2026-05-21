import type { Opportunity } from "../lib/types";
import { ArrowDownRight, ArrowUpRight, Crosshair, DollarSign } from "lucide-react";
import { makeTimeFormatter } from "../lib/format";

interface Props {
  opportunities: Opportunity[];
  // Full-tape timestamps so the date/time formatting matches the charts
  // (the top opportunities can cluster within a day on a multi-day tape).
  axisTimes?: number[];
}

const money = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function pct(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

export default function OpportunityRadar({ opportunities, axisTimes }: Props) {
  const formatTime = makeTimeFormatter(
    axisTimes && axisTimes.length ? axisTimes : opportunities.map((o) => o.time),
  );
  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
            <Crosshair className="w-4 h-4 text-blue-400" />
            Opportunity Radar
          </div>
          <div className="mt-1 text-xs text-gray-500">
            {opportunities.length} qualified windows ranked by conviction
          </div>
        </div>
      </div>

      {opportunities.length === 0 ? (
        <div className="mt-6 rounded-md border border-gray-700/60 bg-gray-900/30 p-4 text-sm text-gray-400">
          Current gates blocked entries for this replay.
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[620px] text-xs">
            <thead>
              <tr className="border-b border-gray-700 text-gray-500">
                <th className="py-2 pr-3 text-left font-medium">Rank</th>
                <th className="px-3 py-2 text-left font-medium">Action</th>
                <th className="px-3 py-2 text-right font-medium">Strength</th>
                <th className="px-3 py-2 text-right font-medium">VPIN</th>
                <th className="px-3 py-2 text-right font-medium">Synth Edge</th>
                <th className="px-3 py-2 text-right font-medium">Size</th>
                <th className="py-2 pl-3 text-right font-medium">Time</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((opportunity) => {
                const isYes = opportunity.side === "yes";
                const SideIcon = isYes ? ArrowUpRight : ArrowDownRight;
                return (
                  <tr
                    key={`${opportunity.rank}-${opportunity.time}`}
                    className="border-b border-gray-700/50 last:border-0 hover:bg-gray-700/20"
                  >
                    <td className="py-2 pr-3 text-gray-500">#{opportunity.rank}</td>
                    <td className="px-3 py-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <span
                          className={`inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md ${
                            isYes ? "bg-emerald-400/10 text-emerald-300" : "bg-red-400/10 text-red-300"
                          }`}
                        >
                          <SideIcon className="h-3.5 w-3.5" />
                        </span>
                        <div className="min-w-0">
                          <div className="font-medium text-gray-200">{opportunity.action}</div>
                          <div className="truncate text-[11px] text-gray-500">
                            {opportunity.rationale}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-gray-200">
                      {pct(opportunity.strength, 0)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      {opportunity.vpin.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      {opportunity.synthEdge === null ? "n/a" : pct(opportunity.synthEdge)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-300">
                      <span className="inline-flex items-center justify-end gap-1">
                        <DollarSign className="h-3 w-3 text-gray-500" />
                        {money.format(opportunity.recommendedSize).replace("$", "")}
                      </span>
                    </td>
                    <td className="py-2 pl-3 text-right text-gray-400">
                      {formatTime(opportunity.time)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
