import { useState } from 'react';

import type { AgentMessage } from '@/types/v0.4';

type Segment = { type: 'text' | 'think'; content: string };

/**
 * 把助手消息内容拆成「正文」与「思考过程(<think>...</think>)」段。
 * - 支持多个 think 块、块前后/之间的正文。
 * - 兼容流式：未闭合的 <think> 把其后内容当作进行中的思考段。
 */
export function parseThinkSegments(raw: string): Segment[] {
  const segments: Segment[] = [];
  const re = /<think>([\s\S]*?)<\/think>/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(raw)) !== null) {
    const before = raw.slice(last, m.index).trim();
    if (before) segments.push({ type: 'text', content: before });
    const think = m[1].trim();
    if (think) segments.push({ type: 'think', content: think });
    last = m.index + m[0].length;
  }
  const rest = raw.slice(last);
  const openIdx = rest.indexOf('<think>');
  if (openIdx !== -1) {
    // 未闭合的 <think>（流式进行中）
    const before = rest.slice(0, openIdx).trim();
    if (before) segments.push({ type: 'text', content: before });
    const think = rest.slice(openIdx + '<think>'.length).trim();
    if (think) segments.push({ type: 'think', content: think });
  } else {
    const tail = rest.trim();
    if (tail) segments.push({ type: 'text', content: tail });
  }
  return segments;
}

function ThinkBlock({ content }: { content: string }) {
  const [open, setOpen] = useState(false); // 默认折叠隐藏
  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600"
      >
        <span aria-hidden="true">{open ? '▾' : '▸'}</span>
        <span>思考过程</span>
      </button>
      {open && (
        <p className="mt-1 whitespace-pre-wrap border-l-2 border-gray-200 pl-2 text-xs text-gray-400">
          {content}
        </p>
      )}
    </div>
  );
}

/** 渲染助手正文：把 <think> 段折叠、正文照常。无外层气泡包裹，可复用于 turn 容器。 */
export function AssistantContent({ content }: { content: string }) {
  const segments = parseThinkSegments(content);
  return (
    <>
      {segments.map((seg, i) =>
        seg.type === 'think' ? (
          <ThinkBlock key={i} content={seg.content} />
        ) : (
          <p key={i} className="whitespace-pre-wrap">
            {seg.content}
          </p>
        ),
      )}
    </>
  );
}

export function ChatMessage({ message }: { message: AgentMessage }) {
  switch (message.role) {
    case 'user':
      return (
        <div className="flex justify-end mb-3">
          <div className="bg-blue-500 text-white px-4 py-2 rounded-lg max-w-[80%] whitespace-pre-wrap">
            {message.content}
          </div>
        </div>
      );

    case 'assistant':
      if (message.content) {
        return (
          <div className="flex justify-start mb-3">
            <div className="bg-white px-4 py-2 rounded-lg shadow max-w-[80%]">
              <AssistantContent content={message.content} />
            </div>
          </div>
        );
      }
      return null;

    case 'tool':
      return null; // tool 消息由父组件通过 ToolCallCard 渲染

    case 'system':
      return (
        <div className="text-center text-gray-500 text-sm italic my-2">
          {message.content}
        </div>
      );
  }
}
