import { useState } from 'react';
import { MoreHorizontal, RotateCcw } from 'lucide-react';

/**
 * v0.7 MessageActions — kebab menu displayed on the right edge of each
 * chat message.  Replay only appears for messages marked as a
 * checkpoint (`last_checkpoint_message_id === messageId`) since
 * non-checkpoint messages can't be safely replayed.
 *
 * **Red-line note (spec §5.4):** the parent `ChatMessage` must NOT be
 * modified to render this; v0.7+ integrations wrap the chat column in
 * a small `<MessageActionsHost>` that overlays the trigger via
 * absolutely positioned portal.  For now this component is exported
 * standalone so future v0.7.1 wiring is a one-line import.
 */

export interface MessageActionsProps {
  sessionId: string;
  messageId: string;
  /** Whether this message is the latest replay checkpoint (spec §6.3). */
  isCheckpoint: boolean;
  /** Triggered when the user confirms the Replay action. */
  onReplay: (messageId: string) => void;
  /** Optional future extensibility hook (copy/quote/retry). */
  onCopy?: (messageId: string) => void;
}

export function MessageActions({
  messageId,
  isCheckpoint,
  onReplay,
  onCopy,
}: MessageActionsProps) {
  const [open, setOpen] = useState(false);
  if (!isCheckpoint && !onCopy) return null;
  if (!isCheckpoint) {
    // We still allow copy-only for non-checkpoints.
    return (
      <button
        type="button"
        onClick={() => onCopy?.(messageId)}
        className="rounded-md border border-border bg-card p-1 text-xs text-fg-muted hover:bg-primary-tint hover:text-primary"
        aria-label="复制"
      >
        ⧉
      </button>
    );
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="消息操作"
        aria-haspopup="menu"
        aria-expanded={open}
        className="rounded-md border border-border bg-card p-1.5 text-fg-muted transition-colors hover:bg-primary-tint hover:text-primary"
      >
        <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-10 mt-1 w-40 rounded-lg border border-glass-border bg-[var(--glass-bg)] p-1 text-sm shadow-popover backdrop-blur-[20px]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onReplay(messageId);
            }}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-fg hover:bg-primary-tint hover:text-primary"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            重放消息
          </button>
        </div>
      )}
    </div>
  );
}
