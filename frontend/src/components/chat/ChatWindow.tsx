"use client";

import { useEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent, type ReactNode } from "react";

import { Button, inputClass } from "@/components/ui";
import { api, errorText } from "@/lib/api";
import type { AttachmentUpload, ChatAttachment, ThreadMessage } from "@/types/api";
import { ComposerFiles, type ComposerFile } from "./Attachments";
import { HistoryMessage, UserBubble } from "./HistoryMessage";

// Khớp backend: attachment_service.MAX_ATTACHMENTS, Settings.max_upload_bytes
const MAX_FILES = 5;
const MAX_BYTES = 10 * 1024 * 1024;
const ACCEPT = ".pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp";

export interface PendingUserMessage {
  text: string;
  attachments: ChatAttachment[];
}

interface Props {
  threadId: string | null; // gắn chi phí phân tích ảnh vào thread đang mở
  history: ThreadMessage[];
  pendingUser: PendingUserMessage | null; // tin nhắn vừa gửi, chưa có trong lịch sử từ server
  live: ReactNode; // nội dung đang stream
  footer: ReactNode; // khung duyệt bản thảo / banner chờ duyệt / lỗi
  composerDisabled: boolean;
  composerHint?: string;
  onSend: (text: string, attachments: ChatAttachment[]) => void;
}

export function ChatWindow(props: Props) {
  const { threadId, history, pendingUser, live, footer, composerDisabled, composerHint, onSend } = props;
  const [text, setText] = useState("");
  const [files, setFiles] = useState<ComposerFile[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);

  // Tự cuộn xuống khi có nội dung mới, trừ khi người dùng đang cuộn lên đọc
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 160;
    if (nearBottom) bottom.current?.scrollIntoView({ block: "end" });
  });

  const uploading = files.some((f) => f.status === "uploading");

  function update(key: string, patch: Partial<ComposerFile>) {
    setFiles((prev) => prev.map((f) => (f.key === key ? { ...f, ...patch } : f)));
  }

  async function upload(file: File, key: string) {
    const form = new FormData();
    form.append("file", file);
    if (threadId) form.append("thread_id", threadId);
    try {
      const res = await api<AttachmentUpload>("/api/v1/agent/attachments", { method: "POST", form });
      const result: ChatAttachment = { kind: res.kind, filename: res.filename, text: res.text, truncated: res.truncated };
      update(key, { status: "ready", result });
    } catch (err) {
      update(key, { status: "error", error: errorText(err) });
    }
  }

  function addFiles(list: Iterable<File>) {
    const added: ComposerFile[] = [];
    for (const file of Array.from(list).slice(0, Math.max(MAX_FILES - files.length, 0))) {
      // Ảnh dán từ clipboard luôn tên "image.png" → thêm giờ để phân biệt
      const name = file.name === "image.png" ? `anh-dan-${Date.now()}.png` : file.name;
      const item: ComposerFile = { key: crypto.randomUUID(), name, status: "uploading" };
      if (file.size > MAX_BYTES) {
        added.push({ ...item, status: "error", error: "Tệp vượt quá 10MB" });
        continue;
      }
      added.push(item);
      void upload(new File([file], name, { type: file.type }), item.key);
    }
    if (added.length) setFiles((prev) => [...prev, ...added]);
  }

  function onPaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const images = Array.from(e.clipboardData.files).filter((f) => f.type.startsWith("image/"));
    if (!images.length) return;
    e.preventDefault();
    addFiles(images);
  }

  function submit() {
    const msg = text.trim();
    if (!msg || composerDisabled || uploading) return;
    onSend(msg, files.flatMap((f) => (f.result ? [f.result] : [])));
    setText("");
    setFiles([]);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  const empty = history.length === 0 && !pendingUser && !live;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-4 px-4 py-6">
          {empty && (
            <div className="py-16 text-center">
              <h1 className="text-lg font-semibold">Bắt đầu một chiến dịch</h1>
              <p className="mx-auto mt-1 max-w-md text-sm text-muted">
                Mô tả sản phẩm, mục tiêu và đối tượng. Agent sẽ tra cứu tài liệu, đề xuất dàn ý để bạn duyệt, rồi viết bản
                thảo Facebook, Instagram và Threads. Có thể đính kèm ảnh (Gemini phân tích nội dung) hoặc tài liệu PDF, DOCX,
                TXT, MD.
              </p>
            </div>
          )}
          {history.map((m) => (
            <HistoryMessage key={m.id} msg={m} />
          ))}
          {pendingUser && <UserBubble text={pendingUser.text} attachments={pendingUser.attachments} />}
          {live}
          {footer}
          <div ref={bottom} />
        </div>
      </div>

      <div className="border-t border-line bg-panel px-4 py-3">
        <div className="mx-auto max-w-4xl">
          <ComposerFiles files={files} onRemove={(key) => setFiles((prev) => prev.filter((f) => f.key !== key))} />
          <div className="flex items-end gap-2">
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(e) => {
                addFiles(e.target.files ?? []);
                e.target.value = "";
              }}
            />
            <Button
              onClick={() => fileInput.current?.click()}
              disabled={composerDisabled || files.length >= MAX_FILES}
              className="h-11"
              title="Đính kèm ảnh hoặc tài liệu (tối đa 5 tệp, 10MB/tệp). Có thể dán ảnh thẳng vào ô chat."
              aria-label="Đính kèm tệp"
            >
              📎
            </Button>
            <textarea
              className={`${inputClass} max-h-48 min-h-11 resize-none`}
              rows={2}
              value={text}
              maxLength={8000}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={onKeyDown}
              onPaste={onPaste}
              disabled={composerDisabled}
              placeholder={composerHint ?? "Mô tả chiến dịch… (Enter để gửi, Shift+Enter xuống dòng, dán ảnh để đính kèm)"}
              aria-label="Brief chiến dịch"
            />
            <Button
              variant="primary"
              onClick={submit}
              disabled={composerDisabled || uploading || !text.trim()}
              className="h-11"
              title={uploading ? "Đang phân tích tệp đính kèm…" : undefined}
            >
              Gửi
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
