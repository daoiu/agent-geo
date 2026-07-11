// v0.6 P1.4 — agent 会话时间线归组：把「一个 user 提问 → 若干 assistant 轮次 +
// 工具调用」合并成 ChatGPT 风格的单条 assistant 容器（推理折叠 + 内嵌工具卡 + 答案）。
import type { AgentMessage } from '@/types/v0.4';
import type { ToolCallDisplay } from '@/components/ToolCallCard';

export type TurnItem =
  | { kind: 'assistant'; content: string }
  | { kind: 'tool'; display: ToolCallDisplay };

export type TurnRow =
  | { kind: 'user'; message: AgentMessage }
  | { kind: 'assistant'; items: TurnItem[] };

function parseMaybeJson(v: unknown): Record<string, unknown> {
  if (typeof v === 'string') {
    try {
      return JSON.parse(v);
    } catch {
      return { raw: v };
    }
  }
  if (v && typeof v === 'object') return v as Record<string, unknown>;
  return {};
}

/**
 * 从持久化消息 + 实时工具调用构建每个工具的展示对象。
 * - assistant.tool_calls 提供 name/arguments
 * - role='tool' 消息（tool_call_id + content=result JSON）提供 result
 * - 实时 liveToolCalls 覆盖（含 pending 状态，最新）
 */
function buildToolDisplays(
  messages: AgentMessage[],
  liveToolCalls: ToolCallDisplay[],
): Map<string, ToolCallDisplay> {
  const displays = new Map<string, ToolCallDisplay>();
  for (const m of messages) {
    if (m.role === 'assistant' && m.tool_calls) {
      for (const tc of m.tool_calls) {
        displays.set(tc.id, {
          tool_call_id: tc.id,
          tool_name: tc.function.name,
          arguments: parseMaybeJson(tc.function.arguments),
          pending: true,
        });
      }
    }
  }
  for (const m of messages) {
    if (m.role === 'tool' && m.tool_call_id) {
      const prev = displays.get(m.tool_call_id) ?? {
        tool_call_id: m.tool_call_id,
        tool_name: m.tool_call_id,
        arguments: {},
      };
      displays.set(m.tool_call_id, {
        ...prev,
        result: parseMaybeJson(m.content),
        pending: false,
      });
    }
  }
  for (const d of liveToolCalls) {
    const prev = displays.get(d.tool_call_id);
    displays.set(d.tool_call_id, { ...prev, ...d });
  }
  return displays;
}

export function buildTurnRows(
  messages: AgentMessage[],
  liveToolCalls: ToolCallDisplay[] = [],
): TurnRow[] {
  const displays = buildToolDisplays(messages, liveToolCalls);
  const rows: TurnRow[] = [];
  let turn: Extract<TurnRow, { kind: 'assistant' }> | null = null;
  const used = new Set<string>();

  const flush = () => {
    if (turn && turn.items.length) rows.push(turn);
    turn = null;
  };

  for (const m of messages) {
    if (m.role === 'user') {
      flush();
      rows.push({ kind: 'user', message: m });
    } else if (m.role === 'assistant') {
      if (!turn) turn = { kind: 'assistant', items: [] };
      if (m.content) turn.items.push({ kind: 'assistant', content: m.content });
      if (m.tool_calls) {
        for (const tc of m.tool_calls) {
          const d = displays.get(tc.id);
          if (d && !used.has(tc.id)) {
            turn.items.push({ kind: 'tool', display: d });
            used.add(tc.id);
          }
        }
      }
    } else if (m.role === 'tool') {
      // 结果一般已由 assistant.tool_calls 关联渲染；仅孤儿 tool 消息才补挂
      if (m.tool_call_id && !used.has(m.tool_call_id)) {
        const d = displays.get(m.tool_call_id);
        if (d) {
          if (!turn) turn = { kind: 'assistant', items: [] };
          turn.items.push({ kind: 'tool', display: d });
          used.add(m.tool_call_id);
        }
      }
    }
    // system 忽略
  }

  // 实时窗口：乐观 assistant 消息的 tool_calls 为 null，工具卡只在 liveToolCalls 里。
  // 按「推理 → 工具 → 答案」的常见顺序，插到最后一个 assistant 内容项之前。
  const liveOnly = liveToolCalls.filter((d) => !used.has(d.tool_call_id));
  if (liveOnly.length) {
    if (!turn) turn = { kind: 'assistant', items: [] };
    const liveItems: TurnItem[] = liveOnly.map((d) => ({ kind: 'tool', display: d }));
    const kinds = turn.items.map((i) => i.kind);
    const lastAssistant = kinds.lastIndexOf('assistant');
    if (turn.items.length >= 2 && lastAssistant > 0) {
      turn.items.splice(lastAssistant, 0, ...liveItems);
    } else {
      turn.items.push(...liveItems);
    }
    for (const d of liveOnly) used.add(d.tool_call_id);
  }

  flush();
  return rows;
}
