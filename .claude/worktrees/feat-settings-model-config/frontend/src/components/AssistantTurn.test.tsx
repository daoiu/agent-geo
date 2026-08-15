import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { AssistantTurn } from './AssistantTurn';
import type { TurnItem } from '@/lib/agentTimeline';

describe('AssistantTurn', () => {
  it('单容器内依次渲染：折叠推理 + 内嵌工具卡 + 答案', async () => {
    const user = userEvent.setup();
    const items: TurnItem[] = [
      { kind: 'assistant', content: '<think>我该 list</think>' },
      {
        kind: 'tool',
        display: {
          tool_call_id: 't1',
          tool_name: 'list_knowledge_bases',
          arguments: {},
          result: { total_count: 1 },
          pending: false,
        },
      },
      { kind: 'assistant', content: '有 1 个知识库' },
    ];
    renderWithRouter(<AssistantTurn items={items} />);

    // 答案可见
    expect(screen.getByText('有 1 个知识库')).toBeInTheDocument();
    // 工具卡在同一容器（默认折叠，展示"工具 ... 返回"）
    expect(screen.getByText(/返回/)).toBeInTheDocument();
    // 推理默认折叠：内容不可见，但有开关
    expect(screen.queryByText('我该 list')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /思考过程/ }));
    expect(screen.getByText('我该 list')).toBeInTheDocument();
  });

  it('空 items 不渲染', () => {
    const { container } = renderWithRouter(<AssistantTurn items={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
