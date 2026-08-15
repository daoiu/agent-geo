import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
 * renderWithRouter — Test helper that wraps the component in a MemoryRouter.
 *
 * Use this for any component test that uses <Link>, <NavLink>, useNavigate,
 * or other react-router hooks/components. It also provides a fresh QueryClient
 * so React Query hooks (useQuery / useQueries) work in tests without sharing
 * cache across test runs.
 *
 * @param ui - the element to render
 * @param options - test options; pass `initialEntries` to control the starting
 *   history stack (default: `['/']`)
 */
export function renderWithRouter(
  ui: ReactElement,
  options?: RenderOptions & { initialEntries?: string[] }
): RenderResult {
  const { initialEntries, ...rest } = options ?? {};
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries ?? ['/']}>{ui}</MemoryRouter>
    </QueryClientProvider>,
    rest
  );
}
