import type { PnlPoint } from "../lib/types";

interface Props {
  trades: PnlPoint[];
}

export default function TradeTable({ trades }: Props) {
  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-3">
        Trade Log ({trades.length} trades)
      </h3>
      <div className="overflow-x-auto max-h-64 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-gray-800">
            <tr className="text-gray-400 border-b border-gray-700">
              <th className="text-left py-2 px-2">#</th>
              <th className="text-left py-2 px-2">Side</th>
              <th className="text-right py-2 px-2">Entry</th>
              <th className="text-right py-2 px-2">Exit</th>
              <th className="text-right py-2 px-2">P&L</th>
              <th className="text-right py-2 px-2">Signal</th>
              <th className="text-right py-2 px-2">VPIN</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr
                key={i}
                className="border-b border-gray-700/50 hover:bg-gray-700/30"
              >
                <td className="py-1.5 px-2 text-gray-500">{i + 1}</td>
                <td className="py-1.5 px-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      t.side === "yes"
                        ? "bg-emerald-400/20 text-emerald-400"
                        : "bg-red-400/20 text-red-400"
                    }`}
                  >
                    {t.side.toUpperCase()}
                  </span>
                </td>
                <td className="py-1.5 px-2 text-right text-gray-300">
                  {t.entryPrice.toFixed(4)}
                </td>
                <td className="py-1.5 px-2 text-right text-gray-300">
                  {t.exitPrice.toFixed(4)}
                </td>
                <td
                  className={`py-1.5 px-2 text-right font-medium ${
                    t.tradePnl >= 0 ? "text-emerald-400" : "text-red-400"
                  }`}
                >
                  ${t.tradePnl.toFixed(2)}
                </td>
                <td className="py-1.5 px-2 text-right text-gray-300">
                  {t.signalStrength.toFixed(3)}
                </td>
                <td className="py-1.5 px-2 text-right text-gray-300">
                  {t.vpinAtEntry.toFixed(3)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
