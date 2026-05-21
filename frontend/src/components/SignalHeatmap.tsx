import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { SignalPoint } from "../lib/types";
import { makeTimeFormatter } from "../lib/format";

interface Props {
  signals: SignalPoint[];
}

export default function SignalHeatmap({ signals }: Props) {
  const tradeSignals = signals.filter((s) => s.shouldTrade);
  const noTradeSignals = signals.filter((s) => !s.shouldTrade);

  const formatTime = makeTimeFormatter(signals.map((s) => s.time));

  const getColor = (strength: number, shouldTrade: boolean) => {
    if (!shouldTrade) return "#4b5563";
    if (strength > 0.8) return "#ef4444";
    if (strength > 0.6) return "#f97316";
    if (strength > 0.4) return "#eab308";
    return "#22c55e";
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-1">
        Signal Heatmap
      </h3>
      <p className="text-xs text-gray-500 mb-3">
        {tradeSignals.length} tradeable signals, {noTradeSignals.length} blocked by
        gates
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="time"
            type="number"
            domain={["dataMin", "dataMax"]}
            tickFormatter={formatTime}
            stroke="#6b7280"
            fontSize={11}
          />
          <YAxis
            dataKey="strength"
            domain={[0, 1]}
            stroke="#6b7280"
            fontSize={11}
            label={{
              value: "Strength",
              angle: -90,
              position: "insideLeft",
              fill: "#9ca3af",
              fontSize: 11,
            }}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              fontSize: 12,
            }}
            labelFormatter={(t: unknown) => formatTime(Number(t))}
            formatter={(value: unknown, name: unknown) => {
              const v = Number(value);
              if (name === "strength") return [v.toFixed(3), "Strength"];
              if (name === "direction") return [v.toFixed(3), "Direction"];
              return [String(value), String(name)];
            }}
          />
          <Scatter data={noTradeSignals} opacity={0.2}>
            {noTradeSignals.map((s, i) => (
              <Cell key={i} fill={getColor(s.strength, false)} r={2} />
            ))}
          </Scatter>
          <Scatter data={tradeSignals}>
            {tradeSignals.map((s, i) => (
              <Cell key={i} fill={getColor(s.strength, true)} r={4} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
