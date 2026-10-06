import { PLATFORM_LABELS, PLATFORMS, type Platform } from "@/types/events";

interface Props {
  active: Platform;
  onChange: (p: Platform) => void;
  /** Ghi chú nhỏ cạnh tên tab (vd. số lỗi fact-check, "đã sửa"). */
  notes?: Partial<Record<Platform, string>>;
}

export function PlatformTabs({ active, onChange, notes = {} }: Props) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-line">
      {PLATFORMS.map((p) => (
        <button
          key={p}
          role="tab"
          type="button"
          aria-selected={active === p}
          onClick={() => onChange(p)}
          className={`-mb-px border-b-2 px-3 py-2 text-sm whitespace-nowrap ${
            active === p ? "border-accent font-medium text-fg" : "border-transparent text-muted hover:text-fg"
          }`}
        >
          {PLATFORM_LABELS[p]}
          {notes[p] && <span className="ml-1.5 text-xs text-muted">{notes[p]}</span>}
        </button>
      ))}
    </div>
  );
}

/** Thread X: các tweet cách nhau bởi dòng trống; trả số tweet vượt 280 ký tự. */
export function overlongTweets(text: string): number {
  return text
    .split(/\n\s*\n/)
    .map((t) => t.trim())
    .filter((t) => [...t].length > 280).length;
}
