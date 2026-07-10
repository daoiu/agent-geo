import { describe, it, expect } from 'vitest';
import { renderWithRouter } from '@/test/renderWithRouter';
import { screen } from '@testing-library/react';
import { TopBar } from './TopBar';

describe('TopBar', () => {
  it('renders brand name and logo', () => {
    renderWithRouter(<TopBar />);
    expect(screen.getByText('GEO 优化系统')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /返回 GEO 优化系统首页/ })).toBeInTheDocument();
  });

  it('renders notification + settings links', () => {
    renderWithRouter(<TopBar />);
    expect(screen.getByRole('link', { name: '通知' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '设置' })).toBeInTheDocument();
  });

  it('renders mobile sidebar toggle when handler provided', () => {
    renderWithRouter(<TopBar onToggleSidebar={() => {}} sidebarOpen={false} />);
    expect(screen.getByRole('button', { name: '打开侧边导航' })).toBeInTheDocument();
  });
});
