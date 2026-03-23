import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from "recharts";
import type { MonteCarloResult } from "../lib/types";

interface Props {
  data: MonteCarloResult;
}

export default function MonteCarloChart({ data }: Props) {
  // Build histogram
  const pnls = data.results.map((r) => r.pnl);
  const min = Math.min(...pnls);
  const max = Math.max(...pnls);
  const binCount = 30;
  const binWidth = (max - min) / binCount || 1;

  const bins: { range: string; count: number; midpoint: number }[] = [];
  for (let i = 0; i < binCount; i++) {
    const lo = min + i * binWidth;
    const hi = lo + binWidth;
    const count = pnls.filter((p) => p >= lo && (i === binCount - 1 ? p <= hi : p < hi)).length;
    bins.push({
      range: `$${lo.toFixed(0)}`,
      count,
      midpoint: (lo + hi) / 2,
    });
  }

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-1">
        Monte Carlo P&L Distribution
      </h3>
      <p className="text-xs text-gray-500 mb-3">
        {data.simulations} simulations —{" "}
        <span className="text-emerald-400">
          {data.summary.profitableRuns} profitable
        </span>{" "}
        ({(data.summary.profitableRunsPct * 100).toFixed(1)}%)
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={bins}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="range"
            stroke="#6b7280"
            fontSize={10}
            interval={Math.floor(binCount / 6)}
          />
          <YAxis stroke="#6b7280" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              fontSize: 12,
            }}
            formatter={(value: any) => [value, "Simulations"]}
          />
          <ReferenceLine x={bins.findIndex((b) => b.midpoint >= 0)} stroke="#6b7280" strokeDasharray="3 3" />
          <Bar dataKey="count" radius={[2, 2, 0, 0]}>
            {bins.map((bin, i) => (
              <Cell
                key={i}
                fill={bin.midpoint >= 0 ? "#10b981" : "#ef4444"}
                fillOpacity={0.7}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Summary stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        {[
          { label: "Mean P&L", value: `$${data.summary.meanPnl.toFixed(2)}`, color: data.summary.meanPnl >= 0 ? "text-emerald-400" : "text-red-400" },
          { label: "Median P&L", value: `$${data.summary.medianPnl.toFixed(2)}`, color: data.summary.medianPnl >= 0 ? "text-emerald-400" : "text-red-400" },
          { label: "5th Percentile", value: `$${data.summary.pnl5th.toFixed(2)}`, color: "text-red-400" },
          { label: "95th Percentile", value: `$${data.summary.pnl95th.toFixed(2)}`, color: "text-emerald-400" },
          { label: "Mean Win Rate", value: `${(data.summary.meanWinRate * 100).toFixed(1)}%`, color: "text-blue-400" },
          { label: "Mean Sharpe", value: data.summary.meanSharpe.toFixed(2), color: "text-purple-400" },
          { label: "Mean Drawdown", value: `${(data.summary.meanDrawdown * 100).toFixed(1)}%`, color: "text-amber-400" },
          { label: "Avg Trades/Sim", value: data.summary.meanTradeCount.toFixed(0), color: "text-gray-300" },
        ].map((s) => (
          <div key={s.label} className="text-center">
            <div className="text-xs text-gray-500">{s.label}</div>
            <div className={`text-sm font-semibold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
