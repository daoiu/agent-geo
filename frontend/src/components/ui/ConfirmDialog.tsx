import { Modal } from './Modal';
import { Button } from './Button';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  /** CTA variant: danger = destructive actions, accent = CTAs. */
  variant?: 'danger' | 'accent' | 'primary';
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

/**
 * ConfirmDialog — Modal + 2 buttons (cancel + confirm).
 * Replaces the v0.4 ConfirmDialog with a unified modal pattern.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmText = '确认',
  cancelText = '取消',
  variant = 'primary',
  onConfirm,
  onCancel,
  loading,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={loading}>
            {cancelText}
          </Button>
          <Button variant={variant} onClick={onConfirm} loading={loading}>
            {confirmText}
          </Button>
        </>
      }
    />
  );
}
