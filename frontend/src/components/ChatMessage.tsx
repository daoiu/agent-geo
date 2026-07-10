import type { AgentMessage } from '@/types/v0.4';

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
              <p className="whitespace-pre-wrap">{message.content}</p>
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