import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function Markdown({ children, streaming = false }: { children: string; streaming?: boolean }) {
  return (
    <div className={`markdown text-sm ${streaming ? "stream-caret" : ""}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
