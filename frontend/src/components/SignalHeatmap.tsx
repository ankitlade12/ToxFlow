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

interface Props {
  signals: SignalPoint[];
}

export default function SignalHeatmap({ signals }: Props) {
  const tradeSignals = signals.filter((s) => s.shouldTrade);
  const noTradeSignals = signals.filter((s) => !s.shouldTrade);

  const formatTime = (t: number) => {
    const d = new Date(t * 1000);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

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
        Y = signal strength, color = intensity.{" "}
        <span className="text-emerald-400">Green</span> = moderate,{" "}
        <span className="text-amber-400">Yellow</span> = strong,{" "}
        <span className="text-red-400">Red</span> = extreme
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
            labelFormatter={(t: any) => formatTime(t)}
            formatter={(value: any, name: any) => {
              const v = Number(value);
              if (name === "strength") return [v.toFixed(3), "Strength"];
              if (name === "direction") return [v.toFixed(3), "Direction"];
              return [value, name];
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
