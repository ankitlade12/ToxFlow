// Time-axis formatting shared by the charts.
//
// Live tapes can span many days, so a plain time-of-day label (e.g. "9:32 AM")
// reads as out-of-order once it wraps past midnight. When the series spans more
// than ~1.5 days we include the calendar date; otherwise we keep it compact.

export function makeTimeFormatter(times: number[]): (t: number) => string {
  const valid = times.filter((t) => Number.isFinite(t));
  const span =
    valid.length > 1 ? Math.abs(valid[valid.length - 1] - valid[0]) : 0;
  const multiDay = span > 36 * 3600; // seconds

  return (t: number) => {
    const d = new Date(t * 1000);
    return multiDay
      ? d.toLocaleString([], {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };
}
