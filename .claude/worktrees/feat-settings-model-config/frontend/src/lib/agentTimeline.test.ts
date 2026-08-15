import { describe, it, expect } from 'vitest';

import { buildTurnRows } from './agentTimeline';
import type { AgentMessage } from '@/types/v0.4';
import type { ToolCallDisplay } from '@/components/ToolCallCard';

let seq = 0;
function msg(partial: Partial<AgentMessage>): AgentMessage {
  seq += 1;
  return {
    id: `m${seq}`,
    session_id: 's1',
    role: 'assistant',
    content: null,
    tool_calls: null,
    tool_call_id: null,
    pending_confirmation: false,
    created_at: new Date().toISOString(),
    ...partial,
  };
}

describe('buildTurnRows', () => {
  it('把 user + 多轮 assistant + 工具归成 [user, assistant容器]', () => {
    const messages: AgentMessage[] = [
      msg({ role: 'user', content: '知识库里有啥' }),
      msg({
        role: 'assistant',
        content: '<think>我该 list</think>',
        tool_calls: [
          { id: 't1', function: { name: 'list_knowledge_bases', arguments: '{}' } },
        ],
      }),
      msg({ role: 'tool', tool_call_id: 't1', content: '{"total_count": 1}' }),
      msg({ role: 'assistant', content: '有 1 个知识库' }),
    ];

    const rows = buildTurnRows(messages, []);
    expect(rows).toHaveLength(2);
    expect(rows[0].kind).toBe('user');

    const turn = rows[1];
    if (turn.kind !== 'assistant') throw new Error('expected assistant turn');
    // 顺序：推理 → 工具卡 → 答案
    expect(turn.items.map((i) => i.kind)).toEqual(['assistant', 'tool', 'assistant']);
    const toolItem = turn.items[1];
    if (toolItem.kind !== 'tool') throw new Error('expected tool');
    expect(toolItem.display.tool_name).toBe('list_knowledge_bases');
    expect(toolItem.display.result).toEqual({ total_count: 1 });
    expect(toolItem.display.pending).toBe(false);
  });

  it('无工具的普通问答归成 [user, assistant(单答案)]', () => {
    const messages: AgentMessage[] = [
      msg({ role: 'user', content: '你好' }),
      msg({ role: 'assistant', content: '你好，有什么可以帮你' }),
    ];
    const rows = buildTurnRows(messages, []);
    expect(rows).toHaveLength(2);
    const turn = rows[1];
    if (turn.kind !== 'assistant') throw new Error('expected assistant turn');
    expect(turn.items).toEqual([{ kind: 'assistant', content: '你好，有什么可以帮你' }]);
  });

  it('实时窗口：assistant.tool_calls 为 null 时用 liveToolCalls 内嵌到答案前', () => {
    const messages: AgentMessage[] = [
      msg({ role: 'user', content: '知识库里有啥' }),
      msg({ role: 'assistant', content: '<think>我该 list</think>' }),
      msg({ role: 'assistant', content: '有 1 个知识库' }),
    ];
    const live: ToolCallDisplay[] = [
      {
        tool_call_id: 't1',
        tool_name: 'list_knowledge_bases',
        arguments: {},
        result: { total_count: 1 },
        pending: false,
      },
    ];
    const rows = buildTurnRows(messages, live);
    const turn = rows[1];
    if (turn.kind !== 'assistant') throw new Error('expected assistant turn');
    expect(turn.items.map((i) => i.kind)).toEqual(['assistant', 'tool', 'assistant']);
  });

  it('实时 pending：只有推理 + 运行中的工具卡', () => {
    const messages: AgentMessage[] = [
      msg({ role: 'user', content: '知识库里有啥' }),
      msg({ role: 'assistant', content: '<think>我该 list</think>' }),
    ];
    const live: ToolCallDisplay[] = [
      { tool_call_id: 't1', tool_name: 'list_knowledge_bases', arguments: {}, pending: true },
    ];
    const rows = buildTurnRows(messages, live);
    const turn = rows[1];
    if (turn.kind !== 'assistant') throw new Error('expected assistant turn');
    expect(turn.items.map((i) => i.kind)).toEqual(['assistant', 'tool']);
    const toolItem = turn.items[1];
    if (toolItem.kind !== 'tool') throw new Error('expected tool');
    expect(toolItem.display.pending).toBe(true);
  });

  it('持久化已关联的工具不会被 liveToolCalls 重复插入', () => {
    const messages: AgentMessage[] = [
      msg({ role: 'user', content: 'q' }),
      msg({
        role: 'assistant',
        content: '<think>x</think>',
        tool_calls: [{ id: 't1', function: { name: 'list_knowledge_bases', arguments: '{}' } }],
      }),
      msg({ role: 'tool', tool_call_id: 't1', content: '{"total_count": 1}' }),
      msg({ role: 'assistant', content: 'done' }),
    ];
    const live: ToolCallDisplay[] = [
      { tool_call_id: 't1', tool_name: 'list_knowledge_bases', arguments: {}, result: { total_count: 1 }, pending: false },
    ];
    const rows = buildTurnRows(messages, live);
    const turn = rows[1];
    if (turn.kind !== 'assistant') throw new Error('expected assistant turn');
    const toolCount = turn.items.filter((i) => i.kind === 'tool').length;
    expect(toolCount).toBe(1);
  });
});
