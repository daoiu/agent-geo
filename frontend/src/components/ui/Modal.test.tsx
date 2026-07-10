import { describe, it, expect, vi } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { Modal } from './Modal';

describe('Modal', () => {
  it('does not render content when open is false', () => {
    renderWithRouter(
      <Modal open={false} onClose={() => {}} title="未打开">
        内容
      </Modal>
    );
    expect(screen.queryByText('未打开')).not.toBeInTheDocument();
  });
});
