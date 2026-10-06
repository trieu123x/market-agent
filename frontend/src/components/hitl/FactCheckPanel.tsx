import { Badge } from "@/components/ui";
import { PLATFORM_LABELS, PLATFORMS, type FactCheckReport, type Platform } from "@/types/events";

const platformLabel = (p: string) => PLATFORM_LABELS[p as Platform] ?? (p || "Chung");

export function issuesByPlatform(report: FactCheckReport | null): Record<Platform, number> {
  const counts = { linkedin: 0, twitter: 0, facebook: 0 };
  for (const i of report?.issues ?? []) {
    if (i.platform in counts) counts[i.platform as Platform] += 1;
  }
  return counts;
}

interface Props {
  report: FactCheckReport | null;
  /** Kênh đang xem: issue của kênh này đứng đầu, kênh khác làm mờ. */
  focus?: Platform;
}

export function FactCheckPanel({ report, focus }: Props) {
  if (!report) return <p className="text-sm text-muted">Không có báo cáo fact-check.</p>;
  const counts = issuesByPlatform(report);
  const issues = [...report.issues].sort(
    (a, b) => Number(b.platform === focus) - Number(a.platform === focus),
  );

  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {report.passed ? <Badge tone="success">✓ Đạt</Badge> : <Badge tone="warning">! Còn {report.issues.length} vấn đề</Badge>}
        <span className="text-xs text-muted">Sau {report.round} vòng tự sửa</span>
      </div>
      {report.summary && <p className="text-muted">{report.summary}</p>}

      <ul className="space-y-1">
        {PLATFORMS.map((p) => (
          <li key={p} className="flex items-center justify-between">
            <span>{PLATFORM_LABELS[p]}</span>
            {counts[p] === 0 ? <Badge tone="success">✓ Pass</Badge> : <Badge tone="warning">✗ {counts[p]} lỗi</Badge>}
          </li>
        ))}
      </ul>

      {issues.length > 0 && (
        <ol className="space-y-2">
          {issues.map((i, idx) => (
            <li
              key={idx}
              className={`rounded-md border border-line p-2.5 ${focus && i.platform !== focus ? "opacity-60" : ""}`}
            >
              <div className="mb-1 flex flex-wrap items-center gap-1.5">
                <Badge tone={i.kind === "fact" ? "danger" : "warning"}>{i.kind === "fact" ? "Số liệu" : "Sáo rỗng"}</Badge>
                <span className="text-xs text-muted">{platformLabel(i.platform)}</span>
              </div>
              <p className="font-medium">“{i.claim}”</p>
              <p className="text-muted">{i.problem}</p>
              {i.suggestion && <p className="mt-1">→ {i.suggestion}</p>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
