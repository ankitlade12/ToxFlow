import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { PnlPoint } from "../lib/types";

interface Props {
  pnlCurve: PnlPoint[];
}

export default function PnlChart({ pnlCurve }: Props) {
  const formatTime = (t: number) => {
    const d = new Date(t * 1000);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const data = pnlCurve.map((p) => ({
    ...p,
    isWin: p.tradePnl > 0,
  }));

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-3">
        Cumulative P&L
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="time"
            tickFormatter={formatTime}
            stroke="#6b7280"
            fontSize={11}
          />
          <YAxis
            stroke="#6b7280"
            fontSize={11}
            tickFormatter={(v) => `$${v}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              fontSize: 12,
            }}
            labelFormatter={(t: any) => formatTime(t)}
            formatter={(value: any, name: any) => {
              const v = Number(value);
              if (name === "pnl") return [`$${v.toFixed(2)}`, "Cumulative P&L"];
              if (name === "tradePnl") return [`$${v.toFixed(2)}`, "Trade P&L"];
              return [value, name];
            }}
          />
          <ReferenceLine y={0} stroke="#6b7280" strokeDasharray="3 3" />
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="pnl"
            stroke="#3b82f6"
            fill="url(#pnlGradient)"
            strokeWidth={2}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
