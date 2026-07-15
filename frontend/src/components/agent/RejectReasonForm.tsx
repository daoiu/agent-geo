import { useState } from 'react';

/**
 * v0.7 RejectReasonForm — nested inside `ConfirmDialog`'s reject branch
 * (spec §7.2).  When the user picks "reject", they must record *why*;
 * the reason enters the next LLM context so the agent is more cautious
 * next time the same tool call comes up (backend P1 #26 already plumbs
 * reason → LLM).
 *
 * **Red-line note (spec §5.4):** the parent `ConfirmDialog` must NOT
 * be modified to render this — the v0.7.1 wiring wraps the existing
 * reject branch with `<RejectReasonForm>` via a portal.  Standalone
 * export so it's ready for one-line integration.
 */

export interface RejectReasonFormProps {
  onSubmit: (reason: string) => void;
  onCancel: () => void;
  maxChars?: number;
  /** Pre-populate from the user's last review. */
  defaultValue?: string;
}

const HELPER_PRESETS = ['成本过高', '数据不准确', '品牌定位不符', '重复任务'];

export function RejectReasonForm({
  onSubmit,
  onCancel,
  maxChars = 500,
  defaultValue = '',
}: RejectReasonFormProps) {
  const [reason, setReason] = useState(defaultValue);
  const canSubmit = reason.trim().length > 0;

  return (
    <form
      className="flex flex-col gap-3 rounded-xl border border-glass-border bg-[var(--glass-bg)] p-4 backdrop-blur-[20px]"
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) onSubmit(reason.trim());
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        <span className="font-medium text-fg">拒绝理由(必填)</span>
        <textarea
          value={reason}
          onChange={(e) => {
            const v = e.target.value;
            setReason(v.length > maxChars ? v.slice(0, maxChars) : v);
          }}
          rows={3}
          maxLength={maxChars}
          placeholder="例如:同主题已发过,本月不再重复……"
          className="rounded-md border border-border bg-card p-2 text-sm text-fg placeholder:text-fg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2 text-xs text-fg-muted">
        <span>常见理由:</span>
        {HELPER_PRESETS.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => setReason(p)}
            className="rounded-pill bg-bg-subtle px-2 py-0.5 hover:bg-primary-tint hover:text-primary"
          >
            {p}
          </button>
        ))}
      </div>
      <div className="flex items-center justify-between text-xs text-fg-muted">
        <span>
          {Math.max(0, reason.length)} / {maxChars}
        </span>
      </div>
      <div className="flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-fg hover:bg-bg-subtle"
        >
          取消
        </button>
        <button
          type="submit"
          disabled={!canSubmit}
          aria-disabled={!canSubmit}
          className="rounded-md bg-danger px-3 py-1.5 text-sm font-medium text-danger-foreground transition-colors duration-400 ease-spring-gentle hover:bg-danger/90 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          确认拒绝
        </button>
      </div>
    </form>
  );
}
