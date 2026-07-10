/**
 * navItems — primary navigation config per v0.6 spec §3.2.
 * Lives in its own file so CommandPalette and SideNav can both import
 * without pulling App.tsx (which embeds the router).
 */
import type { NavItem } from './SideNav';

export const navItems: NavItem[] = [
  { key: 'home', label: '🏠 仪表盘', to: '/' },
  {
    key: 'diag',
    label: '🔍 诊断',
    to: '/new',
    children: [
      { key: 'diag-new', label: '新建诊断', to: '/new' },
      { key: 'diag-history', label: '历史报告', to: '/reports' },
      { key: 'diag-agent', label: '诊断智能体', to: '/agent/diagnose' },
    ],
  },
  {
    key: 'kb',
    label: '📚 知识库',
    to: '/knowledge',
    children: [{ key: 'kb-list', label: '全部 KB', to: '/knowledge' }],
  },
  {
    key: 'gen',
    label: '✍️ 生成',
    to: '/tasks',
    children: [
      { key: 'gen-tasks', label: '生成任务', to: '/tasks' },
      { key: 'gen-new', label: '创建任务', to: '/tasks/new' },
      { key: 'gen-reviews', label: '审核队列', to: '/reviews' },
    ],
  },
  {
    key: 'pub',
    label: '📤 发布',
    to: '/publishes',
    children: [
      { key: 'pub-configs', label: '平台配置', to: '/publishers' },
      { key: 'pub-list', label: '发布历史', to: '/publishes' },
    ],
  },
  {
    key: 'mon',
    label: '📈 监测',
    to: '/monitors',
    children: [
      { key: 'mon-list', label: '品牌监测', to: '/monitors' },
      { key: 'mon-new', label: '新建监测', to: '/monitors/new' },
      { key: 'mon-notif', label: '阈值通知', to: '/notifications' },
    ],
  },
  { key: 'agent', label: '🤖 智能助手', to: '/agent' },
  { key: 'settings', label: '⚙️ 设置', to: '/settings' },
];
