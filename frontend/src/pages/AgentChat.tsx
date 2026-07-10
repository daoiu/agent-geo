import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, confirmAgentActionStream, sendAgentMessageStream } from '@/api/client';
import { ChatMessage } from '@/components/ChatMessage';
import { ToolCallCard, type ToolCallDisplay } from '@/components/ToolCallCard';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import type { AgentEvent, AgentMessage, AgentSessionDetail, PendingConfirmation } from '@/types/v0.4';

export default function AgentChat() {
  const { sessionId = '' } = useParams<{ sessionId: string }>();
  const qc = useQueryClient();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [pending, setPending] = useState<PendingConfirmation | null>(null);
  const [toolCalls, setToolCalls] = useState<Record<string, ToolCallDisplay>>({});

  const { data: session } = useQuery({
    queryKey: ['agent-session', sessionId],
    queryFn: () => api.getAgentSession(sessionId),
    enabled: !!sessionId,
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages, toolCalls]);

  function handleAgentEvent(event: AgentEvent) {
    switch (event.event) {
      case 'assistant_message':
        if (event.content) {
          qc.setQueryData(
            ['agent-session', sessionId],
            (old: AgentSessionDetail | undefined) => {
              if (!old) return old;
              return {
                ...old,
                messages: [
                  ...old.messages,
                  {
                    id: `ast-${Date.now()}-${Math.random()}`,
                    session_id: sessionId,
                    role: 'assistant',
                    content: event.content,
                    tool_calls: null,
                    tool_call_id: null,
                    pending_confirmation: false,
                    created_at: new Date().toISOString(),
                  } as AgentMessage,
                ],
              };
            },
          );
        }
        break;
      case 'tool_call_start':
        setToolCalls((prev) => ({
          ...prev,
          [event.tool_call_id]: {
            tool_call_id: event.tool_call_id,
            tool_name: event.tool_name,
            arguments: event.arguments,
            pending: true,
          },
        }));
        break;
      case 'tool_call_result':
        setToolCalls((prev) => ({
          ...prev,
          [event.tool_call_id]: {
            ...prev[event.tool_call_id],
            result: event.result,
            pending: false,
          },
        }));
        break;
      case 'human_confirmation_required':
        setPending({
          message_id: event.message_id,
          tool_name: event.tool_name,
          arguments: event.arguments,
        });
        break;
      case 'turn_complete':
      case 'max_iterations_reached':
      case 'error':
        break;
    }
  }

  async function send() {
    if (!input.trim() || loading || pending) return;
    const userContent = input.trim();
    setInput('');
    setLoading(true);
    setToolCalls({});

    // 乐观插入 user 消息
    qc.setQueryData(
      ['agent-session', sessionId],
      (old: AgentSessionDetail | undefined) => {
        if (!old) return old;
        return {
          ...old,
          messages: [
            ...old.messages,
            {
              id: `usr-${Date.now()}`,
              session_id: sessionId,
              role: 'user',
              content: userContent,
              tool_calls: null,
              tool_call_id: null,
              pending_confirmation: false,
              created_at: new Date().toISOString(),
            } as AgentMessage,
          ],
        };
      },
    );

    try {
      for await (const event of sendAgentMessageStream(sessionId, userContent)) {
        handleAgentEvent(event);
      }
    } catch (err) {
      console.error('SSE error:', err);
    } finally {
      setLoading(false);
      qc.invalidateQueries({ queryKey: ['agent-session', sessionId] });
    }
  }

  const approve = useMutation({
    mutationFn: async () => {
      const approved = pending!;
      setPending(null);
      setToolCalls({});
      try {
        // 直接消费 SSE 流（API 层在 approved=True 时自动从断点续跑）
        for await (const event of confirmAgentActionStream(
          sessionId,
          approved.message_id,
          true,
        )) {
          handleAgentEvent(event);
        }
      } catch (err) {
        console.error('Resume SSE error:', err);
      } finally {
        qc.invalidateQueries({ queryKey: ['agent-session', sessionId] });
      }
    },
  });

  const cancel = useMutation({
    mutationFn: async () => {
      setPending(null);
      setToolCalls({});
      // cancel 走 JSON 路径（API 返回 cancelled 状态）
      await api.confirmAgentAction(sessionId, pending!.message_id, false);
      qc.invalidateQueries({ queryKey: ['agent-session', sessionId] });
    },
  });

  if (!session) {
    return <div className="p-8 text-center text-gray-500">加载中...</div>;
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <header className="bg-white border-b px-4 py-3 flex justify-between items-center">
        <Link to="/agent" className="text-blue-600 text-sm hover:underline">
          ← 返回
        </Link>
        <h1 className="text-lg font-semibold">{session.title}</h1>
        <div className="w-12" />
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 max-w-3xl mx-auto w-full">
        {session.messages.map((m) => (
          <ChatMessage key={m.id} message={m} />
        ))}
        {Object.values(toolCalls).map((tc) => (
          <ToolCallCard key={tc.tool_call_id} display={tc} />
        ))}
        {loading && (
          <div className="text-gray-500 text-sm italic">agent 思考中...</div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {pending && (
        <ConfirmDialog
          toolName={pending.tool_name}
          arguments={pending.arguments}
          onApprove={() => approve.mutate()}
          onCancel={() => cancel.mutate()}
          pending={approve.isPending || cancel.isPending}
        />
      )}

      <div className="bg-white border-t px-4 py-3">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            disabled={loading || !!pending}
            placeholder={pending ? '等待确认...' : '输入消息（Enter 发送）'}
            className="flex-1 px-3 py-2 border rounded-md disabled:opacity-50"
          />
          <button
            type="button"
            onClick={send}
            disabled={!input.trim() || loading || !!pending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md disabled:opacity-50"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}