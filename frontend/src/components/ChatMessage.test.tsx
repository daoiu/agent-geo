import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ChatMessage, parseThinkSegments } from './ChatMessage';
import type { AgentMessage } from '@/types/v0.4';

function assistant(content: string): AgentMessage {
  return {
    id: 'm1',
    session_id: 's1',
    role: 'assistant',
    content,
    tool_calls: null,
    tool_call_id: null,
    pending_confirmation: false,
    created_at: new Date().toISOString(),
  };
}

describe('ChatMessage <think> 折叠', () => {
  it('默认折叠隐藏思考过程，正文照常显示', () => {
    renderWithRouter(
      <ChatMessage message={assistant('<think>我在推理</think>\n\n目前有 1 个知识库')} />,
    );
    // 思考内容默认不可见
    expect(screen.queryByText('我在推理')).not.toBeInTheDocument();
    // 正文可见
    expect(screen.getByText(/目前有 1 个知识库/)).toBeInTheDocument();
    // 折叠开关存在
    expect(screen.getByRole('button', { name: /思考过程/ })).toBeInTheDocument();
  });

  it('点击开关展开后显示思考过程，再点收起', async () => {
    const user = userEvent.setup();
    renderWithRouter(
      <ChatMessage message={assistant('<think>我在推理</think>\n\n答案')} />,
    );
    const toggle = screen.getByRole('button', { name: /思考过程/ });
    await user.click(toggle);
    expect(screen.getByText('我在推理')).toBeInTheDocument();
    await user.click(toggle);
    expect(screen.queryByText('我在推理')).not.toBeInTheDocument();
  });

  it('无 think 标签的普通助手消息原样显示', () => {
    renderWithRouter(<ChatMessage message={assistant('纯文本回答')} />);
    expect(screen.getByText('纯文本回答')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /思考过程/ })).not.toBeInTheDocument();
  });
});

describe('parseThinkSegments', () => {
  it('拆出 think 段与正文段', () => {
    const segs = parseThinkSegments('<think>思考</think>\n\n正文');
    expect(segs).toEqual([
      { type: 'think', content: '思考' },
      { type: 'text', content: '正文' },
    ]);
  });

  it('未闭合的 <think> 把其后内容当作进行中的思考段（流式）', () => {
    const segs = parseThinkSegments('正文<think>还在想');
    expect(segs).toEqual([
      { type: 'text', content: '正文' },
      { type: 'think', content: '还在想' },
    ]);
  });

  it('多个 think 块', () => {
    const segs = parseThinkSegments('<think>a</think>中间<think>b</think>尾');
    expect(segs).toEqual([
      { type: 'think', content: 'a' },
      { type: 'text', content: '中间' },
      { type: 'think', content: 'b' },
      { type: 'text', content: '尾' },
    ]);
  });
});
