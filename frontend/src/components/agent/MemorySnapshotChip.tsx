import { Brain } from 'lucide-react';
import type { MemorySnapshot } from '@/types/v0.7';

/**
 * v0.7 MemorySnapshotChip — pill rendered near the chat header that
 * shows how many L1 / L2 memories were injected before the current
 * turn. Click is intentionally a no-op here; a future "see memory"
 * drawer is left as a follow-up.
 */

export interface MemorySnapshotChipProps {
  snapshot?: MemorySnapshot;
  className?: string;
}

export function MemorySnapshotChip({ snapshot, className }: MemorySnapshotChipProps) {
  if (!snapshot || snapshot.memories.length === 0) return null;
  const l1 = snapshot.memories.filter((m) => m.source === 'L1').length;
  const l2 = snapshot.memories.filter((m) => m.source === 'L2').length;
  return (
    <span
      className={
        'inline-flex items-center gap-1 rounded-pill bg-primary-tint px-2 py-0.5 text-xs text-primary ' +
        (className ?? '')
      }
      aria-label={`已注入 ${l1} 条 L1 与 ${l2} 条 L2 记忆`}
    >
      <Brain className="h-3 w-3" aria-hidden="true" />
      L1×{l1} · L2×{l2}
    </span>
  );
}
