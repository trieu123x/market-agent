"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { Button, inputClass } from "@/components/ui";
import type { ThreadMessage } from "@/types/api";
import { HistoryMessage, UserBubble } from "./HistoryMessage";

interface Props {
  history: ThreadMessage[];
  pendingUserText: string | null; // tin nhắn vừa gửi, chưa có trong lịch sử từ server
  live: ReactNode; // nội dung đang stream
  footer: ReactNode; // khung duyệt bản thảo / banner chờ duyệt / lỗi
  composerDisabled: boolean;
  composerHint?: string;
  onSend: (text: string) => void;
}

export function ChatWindow({ history, pendingUserText, live, footer, composerDisabled, composerHint, onSend }: Props) {
  const [text, setText] = useState("");
  const bottom = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);

  // Tự cuộn xuống khi có nội dung mới, trừ khi người dùng đang cuộn lên đọc
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (nearBottom) bottom.current?.scrollIntoView({ block: "end" });
  });

  function submit() {
    const msg = text.trim();
    if (!msg || composerDisabled) return;
    onSend(msg);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  const empty = history.length === 0 && !pendingUserText && !live;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-4 px-4 py-6">
          {empty && (
            <div className="py-16 text-center">
              <h1 className="text-lg font-semibold">Bắt đầu một chiến dịch</h1>
              <p className="mx-auto mt-1 max-w-md text-sm text-muted">
                Mô tả sản phẩm, mục tiêu và đối tượng. Agent sẽ tra cứu tài liệu, đề xuất dàn ý để bạn duyệt, rồi viết bản
                thảo LinkedIn, X và Facebook.
              </p>
            </div>
          )}
          {history.map((m) => (
            <HistoryMessage key={m.id} msg={m} />
          ))}
          {pendingUserText && <UserBubble text={pendingUserText} />}
          {live}
          {footer}
          <div ref={bottom} />
        </div>
      </div>

      <div className="border-t border-line bg-panel px-4 py-3">
        <div className="mx-auto flex max-w-4xl items-end gap-2">
          <textarea
            className={`${inputClass} max-h-48 min-h-11 resize-none`}
            rows={2}
            value={text}
            maxLength={8000}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            disabled={composerDisabled}
            placeholder={composerHint ?? "Mô tả chiến dịch… (Enter để gửi, Shift+Enter xuống dòng)"}
            aria-label="Brief chiến dịch"
          />
          <Button variant="primary" onClick={submit} disabled={composerDisabled || !text.trim()} className="h-11">
            Gửi
          </Button>
        </div>
      </div>
    </div>
  );
}
