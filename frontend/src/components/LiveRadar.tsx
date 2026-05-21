import type { ScanRow } from "../lib/types";
import {
  Star,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  TrendingUp,
  TrendingDown,
  Loader2,
} from "lucide-react";

interface Props {
  rows: ScanRow[];
  scanning: boolean;
  watchlist: Set<string>;
  alertedIds: Set<string>;
  selectedId: string | null;
  onToggleWatch: (id: string) => void;
  onAnalyze: (row: ScanRow) => void;
}

function toxicityColor(vpin: number) {
  if (vpin >= 0.85) return "#ef4444";
  if (vpin >= 0.7) return "#f97316";
  if (vpin >= 0.5) return "#eab308";
  return "#22c55e";
}

function biasTone(bias: string) {
  if (bias === "YES") return "text-emerald-300";
  if (bias === "NO") return "text-red-300";
  return "text-gray-400";
}

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
});

export default function LiveRadar({
  rows,
  scanning,
  watchlist,
  alertedIds,
  selectedId,
  onToggleWatch,
  onAnalyze,
}: Props) {
  if (rows.length === 0 && !scanning) {
    return (
      <div className="rounded-md border border-gray-700/60 bg-gray-900/30 p-6 text-center text-sm text-gray-400">
        No markets with enough live activity to score. Try a broader search
        (e.g. leave it empty for top-volume markets).
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-xs">
        <thead>
          <tr className="border-b border-gray-700 text-gray-500">
            <th className="py-2 pl-2 pr-1 text-left font-medium">#</th>
            <th className="px-1 py-2 text-left font-medium"></th>
            <th className="px-2 py-2 text-left font-medium">Market</th>
            <th className="px-2 py-2 text-left font-medium" title="VPIN adjusted for sample size & spike density">Toxicity</th>
            <th className="px-2 py-2 text-center font-medium">Flow</th>
            <th className="px-2 py-2 text-right font-medium">Momentum</th>
            <th className="px-2 py-2 text-right font-medium">Spikes</th>
            <th className="px-2 py-2 text-right font-medium">Informed</th>
            <th className="px-2 py-2 text-right font-medium">Price</th>
            <th className="px-2 py-2 text-right font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const watched = watchlist.has(r.conditionId);
            const alerted = alertedIds.has(r.conditionId);
            const selected = selectedId === r.conditionId;
            const isYes = r.dvpin >= 0.05;
            const isNo = r.dvpin <= -0.05;
            const FlowIcon = isYes ? ArrowUpRight : isNo ? ArrowDownRight : Minus;
            return (
              <tr
                key={r.conditionId}
                className={`border-b border-gray-700/50 last:border-0 transition-colors ${
                  selected ? "bg-blue-500/10" : "hover:bg-gray-700/20"
                } ${alerted ? "ring-1 ring-inset ring-amber-400/40" : ""}`}
              >
                <td className="py-2.5 pl-2 pr-1 text-gray-500">{i + 1}</td>
                <td className="px-1 py-2.5">
                  <button
                    onClick={() => onToggleWatch(r.conditionId)}
                    title={watched ? "Unwatch" : "Watch for alerts"}
                    className="text-gray-500 hover:text-amber-300"
                  >
                    <Star
                      className={`h-3.5 w-3.5 ${watched ? "fill-amber-400 text-amber-400" : ""}`}
                    />
                  </button>
                </td>
                <td className="max-w-[260px] px-2 py-2.5">
                  <div className="truncate font-medium text-gray-200" title={r.question}>
                    {r.question}
                  </div>
                  {r.eventTitle && r.eventTitle !== r.question && (
                    <div className="truncate text-[11px] text-gray-500">
                      {r.eventTitle}
                    </div>
                  )}
                </td>
                <td className="px-2 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-20 rounded-full bg-gray-700">
                      <div
                        className="h-1.5 rounded-full"
                        style={{
                          width: `${Math.min(r.toxicityScore * 100, 100)}%`,
                          backgroundColor: toxicityColor(r.toxicityScore),
                        }}
                      />
                    </div>
                    <span
                      className="font-mono font-medium"
                      style={{ color: toxicityColor(r.toxicityScore) }}
                    >
                      {r.toxicityScore.toFixed(3)}
                    </span>
                    {r.divergence && (
                      <span className="rounded bg-amber-400/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-300">
                        DIV
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 text-[10px] text-gray-500">
                    VPIN {r.vpin.toFixed(2)} · {r.numTrades.toLocaleString()} trades
                  </div>
                </td>
                <td className="px-2 py-2.5 text-center">
                  <span
                    className={`inline-flex items-center gap-1 font-medium ${biasTone(
                      r.flowBias,
                    )}`}
                  >
                    <FlowIcon className="h-3.5 w-3.5" />
                    {r.flowBias}
                  </span>
                </td>
                <td className="px-2 py-2.5 text-right">
                  <span
                    className={`inline-flex items-center justify-end gap-1 ${
                      r.vpinMomentum > 0.01
                        ? "text-red-300"
                        : r.vpinMomentum < -0.01
                          ? "text-emerald-300"
                          : "text-gray-400"
                    }`}
                  >
                    {r.vpinMomentum > 0.01 ? (
                      <TrendingUp className="h-3 w-3" />
                    ) : r.vpinMomentum < -0.01 ? (
                      <TrendingDown className="h-3 w-3" />
                    ) : null}
                    {r.vpinMomentum >= 0 ? "+" : ""}
                    {r.vpinMomentum.toFixed(3)}
                  </span>
                </td>
                <td className="px-2 py-2.5 text-right text-gray-300">{r.spikeCount}</td>
                <td className="px-2 py-2.5 text-right text-gray-300">
                  {(r.smartVolumePct * 100).toFixed(0)}%
                </td>
                <td className="px-2 py-2.5 text-right text-gray-400">
                  {r.latestPrice != null ? `${(r.latestPrice * 100).toFixed(1)}c` : "—"}
                  <div className="text-[10px] text-gray-600">
                    ${compact.format(r.volume)}
                  </div>
                </td>
                <td className="px-2 py-2.5 text-right">
                  <button
                    onClick={() => onAnalyze(r)}
                    className="rounded-md bg-blue-600/80 px-2.5 py-1 text-[11px] font-medium text-white hover:bg-blue-500"
                  >
                    Analyze
                  </button>
                </td>
              </tr>
            );
          })}
          {scanning && rows.length === 0 && (
            <tr>
              <td colSpan={10} className="py-10 text-center text-gray-400">
                <Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin text-blue-400" />
                Scanning live markets…
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
