import { useEffect, useState, useCallback, type Dispatch, type SetStateAction } from 'react';
import { useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from '@/components/ui/command';
import { navItems } from '@/components/layout/navConfig.tsx';
import type { NavItem } from './SideNav';

interface PaletteEntry {
  label: string;
  to: string;
  group: string;
}

function flattenNav(items: NavItem[], group = ''): PaletteEntry[] {
  const out: PaletteEntry[] = [];
  for (const item of items) {
    if (item.children && item.children.length > 0) {
      out.push(...flattenNav(item.children, item.label));
    } else {
      out.push({
        label: stripEmoji(item.label),
        to: item.to,
        group: group || '主入口',
      });
    }
  }
  return out;
}

function stripEmoji(label: string): string {
  // Remove leading emoji + spaces, keep Chinese label readable in the palette
  return label.replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]\s*/u, '').trim();
}

const ENTRIES = flattenNav(navItems);

/**
 * CommandPalette — global ⌘K / Ctrl K launcher.
 * Lists every reachable route as a flat searchable list.
 * The hotkey listener is mounted once near the root (in LayoutShell).
 */
export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const navigate = useNavigate();
  const go = useCallback(
    (to: string) => {
      onOpenChange(false);
      navigate(to);
    },
    [navigate, onOpenChange],
  );

  // Group entries by their top-level group for visual hierarchy
  const grouped = ENTRIES.reduce<Record<string, PaletteEntry[]>>((acc, e) => {
    (acc[e.group] ||= []).push(e);
    return acc;
  }, {});

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 shadow-lg max-w-lg">
        <DialogTitle className="sr-only">命令面板</DialogTitle>
        <Command label="命令面板">
          <CommandInput placeholder="搜索页面、跳转、命令…" autoFocus />
          <CommandList>
            <CommandEmpty>没有匹配项。</CommandEmpty>
            {Object.entries(grouped).map(([group, items]) => (
              <CommandGroup key={group} heading={group}>
                {items.map((entry) => (
                  <CommandItem
                    key={entry.to}
                    value={`${entry.label} ${entry.to}`}
                    onSelect={() => go(entry.to)}
                  >
                    {entry.label}
                    <CommandShortcut>{entry.to}</CommandShortcut>
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

/**
 * useCommandPaletteHotkey — listens for ⌘K (Mac) / Ctrl K (Win/Linux)
 * and calls `setOpen(true)` when matched.
 */
export function useCommandPaletteHotkey(
  setOpen: Dispatch<SetStateAction<boolean>>
) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v: boolean) => !v);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [setOpen]);
}

export function useCommandPalette(): [boolean, (v: boolean) => void] {
  const [open, setOpen] = useState(false);
  useCommandPaletteHotkey(setOpen);
  return [open, setOpen];
}
