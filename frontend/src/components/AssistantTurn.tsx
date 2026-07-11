import { AssistantContent } from './ChatMessage';
import { ToolCallCard } from './ToolCallCard';
import type { TurnItem } from '@/lib/agentTimeline';

/**
 * 一个 assistant 轮次的统一容器（ChatGPT 风格）：单个左对齐气泡里依次堆叠
 * 折叠推理、内嵌工具卡、最终答案，而不是每步一条顶层气泡。
 */
export function AssistantTurn({ items }: { items: TurnItem[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex justify-start mb-3">
      <div className="bg-white px-4 py-2 rounded-lg shadow max-w-[80%] space-y-1">
        {items.map((it, i) =>
          it.kind === 'assistant' ? (
            <AssistantContent key={`a-${i}`} content={it.content} />
          ) : (
            <ToolCallCard key={`t-${it.display.tool_call_id}`} display={it.display} />
          ),
        )}
      </div>
    </div>
  );
}
