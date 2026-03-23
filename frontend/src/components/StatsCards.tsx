import type { BacktestStats } from "../lib/types";
import {
  TrendingUp,
  TrendingDown,
  Target,
  DollarSign,
  Activity,
  BarChart3,
} from "lucide-react";

interface Props {
  stats: BacktestStats;
  outcome: string;
}

export default function StatsCards({ stats, outcome }: Props) {
  const cards = [
    {
      label: "Total P&L",
      value: `$${stats.totalPnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
      icon: stats.totalPnl >= 0 ? TrendingUp : TrendingDown,
      color: stats.totalPnl >= 0 ? "text-emerald-400" : "text-red-400",
      bg: stats.totalPnl >= 0 ? "bg-emerald-400/10" : "bg-red-400/10",
    },
    {
      label: "Win Rate",
      value: `${(stats.winRate * 100).toFixed(1)}%`,
      icon: Target,
      color: stats.winRate >= 0.5 ? "text-emerald-400" : "text-amber-400",
      bg: stats.winRate >= 0.5 ? "bg-emerald-400/10" : "bg-amber-400/10",
    },
    {
      label: "Profit Factor",
      value: stats.profitFactor.toFixed(2),
      icon: BarChart3,
      color: stats.profitFactor >= 1 ? "text-emerald-400" : "text-red-400",
      bg: stats.profitFactor >= 1 ? "bg-emerald-400/10" : "bg-red-400/10",
    },
    {
      label: "Trades",
      value: stats.numTrades.toString(),
      icon: Activity,
      color: "text-blue-400",
      bg: "bg-blue-400/10",
    },
    {
      label: "Fees Paid",
      value: `$${stats.totalFees.toFixed(2)}`,
      icon: DollarSign,
      color: "text-orange-400",
      bg: "bg-orange-400/10",
    },
    {
      label: "Outcome",
      value: outcome.toUpperCase(),
      icon: Target,
      color: outcome === "yes" ? "text-emerald-400" : "text-red-400",
      bg: outcome === "yes" ? "bg-emerald-400/10" : "bg-red-400/10",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4"
        >
          <div className="flex items-center gap-2 mb-2">
            <div className={`p-1.5 rounded ${card.bg}`}>
              <card.icon className={`w-3.5 h-3.5 ${card.color}`} />
            </div>
            <span className="text-xs text-gray-400">{card.label}</span>
          </div>
          <div className={`text-lg font-semibold ${card.color}`}>
            {card.value}
          </div>
        </div>
      ))}
    </div>
  );
}
