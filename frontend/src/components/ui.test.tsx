import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { StateMessage } from './ui';

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));

describe('StateMessage', () => {
  it('shows plain-text pipeline errors instead of replacing them with a generic message', () => {
    render(<StateMessage error="No live legal source corpus is promoted yet." onRetry={vi.fn()} />);
    expect(screen.getByRole('alert')).toHaveTextContent('No live legal source corpus is promoted yet.');
    expect(screen.queryByText('Something went wrong.')).not.toBeInTheDocument();
  });
});
