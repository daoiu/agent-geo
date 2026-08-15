// v0.4 Agent 类型定义

export type AgentMessageRole = 'user' | 'assistant' | 'tool' | 'system';

export interface AgentSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface AgentToolCall {
  id: string;
  type?: string;
  function: {
    name: string;
    arguments: string | Record<string, unknown>;
  };
}

export interface AgentMessage {
  id: string;
  session_id: string;
  role: AgentMessageRole;
  content: string | null;
  tool_calls: AgentToolCall[] | null;
  tool_call_id: string | null;
  pending_confirmation: boolean;
  created_at: string;
}

export interface AgentSessionDetail extends AgentSession {
  messages: AgentMessage[];
}

export interface PendingConfirmation {
  message_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
}

// SSE 事件类型
export type AgentEvent =
  | { event: 'assistant_message'; content: string }
  | {
      event: 'tool_call_start';
      tool_call_id: string;
      tool_name: string;
      arguments: Record<string, unknown>;
    }
  | {
      event: 'tool_call_result';
      tool_call_id: string;
      result: Record<string, unknown>;
    }
  | {
      event: 'human_confirmation_required';
      message_id: string;
      tool_name: string;
      arguments: Record<string, unknown>;
    }
  | { event: 'turn_complete' }
  | { event: 'max_iterations_reached'; message: string }
  | { event: 'error'; message: string };