import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { VPINPoint, PricePoint } from "../lib/types";

interface Props {
  vpinSeries: VPINPoint[];
  priceSeries: PricePoint[];
}

export default function VPINChart({ vpinSeries, priceSeries }: Props) {
  // Downsample price to match VPIN timestamps for overlay
  const priceMap = new Map<number, number>();
  for (const p of priceSeries) {
    priceMap.set(Math.round(p.time), p.price);
  }

  const data = vpinSeries.map((v) => {
    // Find nearest price point
    const roundedTime = Math.round(v.time);
    let price = priceMap.get(roundedTime);
    if (!price) {
      // Find closest
      let minDist = Infinity;
      for (const p of priceSeries) {
        const dist = Math.abs(p.time - v.time);
        if (dist < minDist) {
          minDist = dist;
          price = p.price;
        }
        if (dist > minDist) break;
      }
    }
    return {
      time: v.time,
      vpin: v.vpin,
      dvpin: v.dvpin,
      zScore: v.zScore,
      price: price ?? 0.5,
      isSpike: v.isSpike,
    };
  });

  const formatTime = (t: number) => {
    const d = new Date(t * 1000);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-3">
        VPIN & Market Price
      </h3>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey="time"
            tickFormatter={formatTime}
            stroke="#6b7280"
            fontSize={11}
          />
          <YAxis
            yAxisId="vpin"
            domain={[0, 1]}
            stroke="#6b7280"
            fontSize={11}
            label={{
              value: "VPIN",
              angle: -90,
              position: "insideLeft",
              fill: "#9ca3af",
              fontSize: 11,
            }}
          />
          <YAxis
            yAxisId="price"
            orientation="right"
            domain={[0, 1]}
            stroke="#6b7280"
            fontSize={11}
            label={{
              value: "Price",
              angle: 90,
              position: "insideRight",
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
            formatter={(value: any, name: any) => [
              Number(value).toFixed(4),
              name === "vpin"
                ? "VPIN"
                : name === "dvpin"
                  ? "D-VPIN"
                  : "Price",
            ]}
          />
          <ReferenceLine
            yAxisId="vpin"
            y={0.6}
            stroke="#ef4444"
            strokeDasharray="5 5"
            label={{ value: "Toxic", fill: "#ef4444", fontSize: 10 }}
          />
          <Area
            yAxisId="vpin"
            type="monotone"
            dataKey="vpin"
            stroke="#3b82f6"
            fill="#3b82f680"
            strokeWidth={2}
            dot={false}
            name="vpin"
          />
          <Line
            yAxisId="vpin"
            type="monotone"
            dataKey="dvpin"
            stroke="#10b981"
            strokeWidth={1.5}
            dot={false}
            name="dvpin"
          />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="price"
            stroke="#f59e0b"
            strokeWidth={1.5}
            dot={false}
            name="price"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
