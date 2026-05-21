import type { SmartMoney } from "../lib/types";
import {
  Users,
  ArrowUpRight,
  ArrowDownRight,
  Crosshair,
  Zap,
  AlertTriangle,
} from "lucide-react";

interface Props {
  smartMoney: SmartMoney;
}

const money = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function pct(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function biasTone(bias: string) {
  if (bias === "YES") return "text-emerald-300 bg-emerald-400/10 border-emerald-400/30";
  if (bias === "NO") return "text-red-300 bg-red-400/10 border-red-400/30";
  return "text-gray-300 bg-gray-700/60 border-gray-600";
}

export default function SmartMoneyPanel({ smartMoney }: Props) {
  const sm = smartMoney;
  const hasData = sm.totalWallets > 0;

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Users className="w-4 h-4 text-blue-400" />
          Smart Money Flow
        </div>
        <div
          className={`rounded-md border px-2.5 py-1 text-xs font-medium ${biasTone(
            sm.flowBias,
          )}`}
        >
          Informed bias: {sm.flowBias}
        </div>
      </div>

      {!hasData ? (
        <div className="mt-6 rounded-md border border-gray-700/60 bg-gray-900/30 p-4 text-sm text-gray-400">
          Not enough wallet-tagged flow to classify on this tape.
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <Stat
              label="Informed volume"
              value={pct(sm.smartVolumePct, 0)}
              sub={`${sm.informedWallets}/${sm.totalWallets} wallets`}
            />
            <Stat
              label="Conviction"
              value={pct(sm.convictionScore, 0)}
              sub="one-sidedness"
            />
            <Stat
              label="Net lean"
              value={sm.smartDirection >= 0 ? "YES" : "NO"}
              sub={`${(sm.smartDirection >= 0 ? "+" : "")}${(sm.smartDirection * 100).toFixed(0)}`}
              tone={sm.smartDirection >= 0 ? "pos" : "neg"}
            />
          </div>

          {/* Informed vs retail direction bars */}
          <div className="mt-4 space-y-2 border-t border-gray-700/50 pt-4">
            <DirectionBar label="Informed" value={sm.smartDirection} />
            <DirectionBar label="Retail" value={sm.retailDirection} muted />
          </div>

          {sm.divergence && (
            <div className="mt-4 flex items-start gap-2 rounded-md border border-amber-400/30 bg-amber-400/10 p-3 text-xs text-amber-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                <span className="font-semibold">Divergence detected.</span>{" "}
                Informed wallets are leaning {sm.flowBias} while retail leans the
                other way — the classic informed-vs-crowd setup.
              </span>
            </div>
          )}

          {/* Leaderboard */}
          {sm.leaders.length > 0 && (
            <div className="mt-4 border-t border-gray-700/50 pt-4">
              <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">
                Top informed wallets
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[460px] text-xs">
                  <thead>
                    <tr className="border-b border-gray-700 text-gray-500">
                      <th className="py-2 pr-3 text-left font-medium">Wallet</th>
                      <th className="px-2 py-2 text-left font-medium">Side</th>
                      <th className="px-2 py-2 text-right font-medium">Volume</th>
                      <th className="px-2 py-2 text-right font-medium" title="Directional conviction">
                        <span className="inline-flex items-center gap-1">
                          <Crosshair className="h-3 w-3" /> Conv
                        </span>
                      </th>
                      <th className="px-2 py-2 text-right font-medium" title="Price leadership">
                        <span className="inline-flex items-center gap-1">
                          <Zap className="h-3 w-3" /> Lead
                        </span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {sm.leaders.map((w) => {
                      const isYes = w.side === "YES";
                      const SideIcon = isYes ? ArrowUpRight : ArrowDownRight;
                      return (
                        <tr
                          key={w.address}
                          className="border-b border-gray-700/50 last:border-0 hover:bg-gray-700/20"
                        >
                          <td className="py-2 pr-3 font-mono text-gray-300">
                            {w.address.slice(0, 6)}…{w.address.slice(-4)}
                          </td>
                          <td className="px-2 py-2">
                            <span
                              className={`inline-flex items-center gap-1 ${
                                isYes ? "text-emerald-300" : "text-red-300"
                              }`}
                            >
                              <SideIcon className="h-3 w-3" />
                              {w.side}
                            </span>
                          </td>
                          <td className="px-2 py-2 text-right text-gray-300">
                            {money.format(w.volume)}
                          </td>
                          <td className="px-2 py-2 text-right text-gray-300">
                            {pct(w.conviction, 0)}
                          </td>
                          <td
                            className={`px-2 py-2 text-right ${
                              w.leadership > 0.1
                                ? "text-emerald-300"
                                : w.leadership < -0.1
                                  ? "text-red-300"
                                  : "text-gray-400"
                            }`}
                          >
                            {w.leadership >= 0 ? "+" : ""}
                            {w.leadership.toFixed(2)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "pos" | "neg";
}) {
  const color =
    tone === "pos" ? "text-emerald-300" : tone === "neg" ? "text-red-300" : "text-gray-200";
  return (
    <div className="min-w-0">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${color}`}>{value}</div>
      {sub && <div className="text-[11px] text-gray-500">{sub}</div>}
    </div>
  );
}

function DirectionBar({
  label,
  value,
  muted,
}: {
  label: string;
  value: number;
  muted?: boolean;
}) {
  // value in [-1, 1]; center is neutral. Render a left/right fill from center.
  const magnitude = Math.min(Math.abs(value), 1) * 50; // half-width %
  const isYes = value >= 0;
  const color = muted
    ? isYes
      ? "bg-emerald-400/40"
      : "bg-red-400/40"
    : isYes
      ? "bg-emerald-400"
      : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-xs text-gray-500">{label}</span>
      <div className="relative h-2 flex-1 rounded-full bg-gray-700">
        <div className="absolute left-1/2 top-0 h-2 w-px bg-gray-500" />
        <div
          className={`absolute top-0 h-2 ${color} ${isYes ? "rounded-r-full" : "rounded-l-full"}`}
          style={{
            left: isYes ? "50%" : `${50 - magnitude}%`,
            width: `${magnitude}%`,
          }}
        />
      </div>
      <span className="w-10 shrink-0 text-right text-xs text-gray-400">
        {value >= 0 ? "+" : ""}
        {(value * 100).toFixed(0)}
      </span>
    </div>
  );
}
