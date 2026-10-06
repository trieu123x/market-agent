export const formatUsd = (v: number) =>
  `$${v.toLocaleString("en-US", { minimumFractionDigits: v > 0 && v < 0.01 ? 6 : 4, maximumFractionDigits: 6 })}`;

export const formatInt = (v: number) => v.toLocaleString("vi-VN");

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" });

export const formatBytes = (n: number | null) => {
  if (n == null) return "–";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
};
