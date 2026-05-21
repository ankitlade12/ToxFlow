import type { SingleBacktestResult } from "../lib/types";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Bot,
  Clock3,
  DollarSign,
  Gauge,
  ShieldCheck,
} from "lucide-react";

interface Props {
  // Narrowed so both the synthetic backtest and live analysis results work.
  result: Pick<
    SingleBacktestResult,
    "decisionBrief" | "riskSummary" | "marketQuality" | "benchmark"
  >;
}

const money = new Intl.NumberFormat(undefined, {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

function pct(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function formatAge(seconds: number | null) {
  if (seconds === null) return "No entry";
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

function formatPrice(price: number) {
  return `${(price * 100).toFixed(1)}c`;
}

function confidenceTone(label: string) {
  if (label === "High") return "text-emerald-300 bg-emerald-400/10 border-emerald-400/30";
  if (label === "Medium") return "text-amber-300 bg-amber-400/10 border-amber-400/30";
  return "text-gray-300 bg-gray-700/60 border-gray-600";
}

export default function DecisionBrief({ result }: Props) {
  const { decisionBrief, riskSummary, marketQuality, benchmark } = result;
  const isYes = decisionBrief.recommendedSide === "yes";
  const isNo = decisionBrief.recommendedSide === "no";
  const ActionIcon = isNo ? ArrowDownRight : isYes ? ArrowUpRight : Activity;
  const actionColor = isNo
    ? "text-red-300"
    : isYes
      ? "text-emerald-300"
      : "text-blue-300";

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
      <section className="xl:col-span-5 bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-gray-500">
              <Bot className="w-3.5 h-3.5" />
              Decision Brief
            </div>
            <div className={`mt-3 flex items-center gap-2 text-2xl font-semibold ${actionColor}`}>
              <ActionIcon className="w-6 h-6 shrink-0" />
              <span className="truncate">{decisionBrief.action}</span>
            </div>
          </div>
          <div
            className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium ${confidenceTone(
              decisionBrief.confidenceLabel,
            )}`}
          >
            {decisionBrief.confidenceLabel} confidence
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3 border-t border-gray-700/50 pt-4">
          <Metric label="Price" value={formatPrice(decisionBrief.latestPrice)} />
          <Metric label="Flow Bias" value={decisionBrief.flowBias} />
          <Metric label="Signal Age" value={formatAge(decisionBrief.signalAgeSeconds)} />
        </div>

        <div className="mt-4 space-y-2 border-t border-gray-700/50 pt-4">
          {decisionBrief.reasons.map((reason) => (
            <div key={reason} className="flex items-start gap-2 text-sm text-gray-300">
              <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
              <span>{reason}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="xl:col-span-3 bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-gray-500">
          <ShieldCheck className="w-3.5 h-3.5" />
          Risk Guard
        </div>
        <div className="mt-4 space-y-3">
          <MetricRow
            label="Suggested size"
            value={money.format(riskSummary.suggestedPosition)}
            icon={DollarSign}
          />
          <MetricRow
            label="Capital at risk"
            value={pct(riskSummary.capitalAtRiskPct)}
            icon={Gauge}
          />
          <MetricRow
            label="Stop / Target"
            value={`${pct(riskSummary.stopLossPct)} / ${pct(riskSummary.profitTargetPct)}`}
            icon={Activity}
          />
          <MetricRow
            label="Max hold"
            value={`${Math.round(riskSummary.maxHoldSeconds / 60)}m`}
            icon={Clock3}
          />
        </div>
        <div className="mt-4 border-t border-gray-700/50 pt-3">
          {riskSummary.riskFlags.map((flag) => (
            <div key={flag} className="flex items-start gap-2 text-xs text-gray-400">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
              <span>{flag}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="xl:col-span-2 bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-gray-500">
          <Gauge className="w-3.5 h-3.5" />
          Market Quality
        </div>
        <div className="mt-4">
          <div className="flex items-end justify-between">
            <span className="text-2xl font-semibold text-blue-300">
              {pct(marketQuality.liquidityScore, 0)}
            </span>
            <span className="rounded-md bg-gray-700/60 px-2 py-1 text-xs text-gray-300">
              {marketQuality.toxicityRegime}
            </span>
          </div>
          <div className="mt-3 h-2 rounded-full bg-gray-700">
            <div
              className="h-2 rounded-full bg-blue-400"
              style={{ width: `${Math.min(marketQuality.liquidityScore * 100, 100)}%` }}
            />
          </div>
        </div>
        <div className="mt-4 space-y-2 text-sm">
          <MetricPair label="Volume" value={money.format(marketQuality.totalVolume)} />
          <MetricPair label="Wallets" value={marketQuality.uniqueWallets.toString()} />
          <MetricPair label="VPIN spikes" value={marketQuality.spikeCount.toString()} />
          <MetricPair label="Top wallets" value={pct(marketQuality.topWalletVolumePct)} />
        </div>
      </section>

      <section className="xl:col-span-2 bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-gray-500">
          <BarChart3 className="w-3.5 h-3.5" />
          Model Lift
        </div>
        {benchmark ? (
          <div className="mt-4 space-y-3">
            <div
              className={`text-2xl font-semibold ${
                benchmark.compositeLift >= 0 ? "text-emerald-300" : "text-red-300"
              }`}
            >
              {money.format(benchmark.compositeLift)}
            </div>
            <MetricPair label="VPIN only" value={money.format(benchmark.vpinOnlyPnl)} />
            <MetricPair label="Win lift" value={pct(benchmark.winRateDelta)} />
            <MetricPair label="Trade delta" value={benchmark.tradeDelta.toString()} />
          </div>
        ) : (
          <div className="mt-4 text-sm text-gray-400">
            Synthesis overlay is off for this run.
          </div>
        )}
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-gray-200">{value}</div>
    </div>
  );
}

function MetricRow({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Activity;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-2 text-sm text-gray-400">
        <Icon className="h-4 w-4 shrink-0 text-gray-500" />
        <span className="truncate">{label}</span>
      </div>
      <span className="shrink-0 text-sm font-medium text-gray-200">{value}</span>
    </div>
  );
}

function MetricPair({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-200">{value}</span>
    </div>
  );
}
