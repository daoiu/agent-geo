import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';

/**
 * renderWithRouter — Test helper that wraps the component in a MemoryRouter.
 *
 * Use this for any component test that uses <Link>, <NavLink>, useNavigate,
 * or other react-router hooks/components.
 *
 * @param ui - the element to render
 * @param options - testid + render options; pass `initialEntries` to control
 *   the starting history stack (default: `['/']`)
 */
export function renderWithRouter(
  ui: ReactElement,
  options?: RenderOptions & { initialEntries?: string[] }
): RenderResult {
  const { initialEntries, ...rest } = options ?? {};
  return render(
    <MemoryRouter initialEntries={initialEntries ?? ['/']}>{ui}</MemoryRouter>,
    rest
  );
}
