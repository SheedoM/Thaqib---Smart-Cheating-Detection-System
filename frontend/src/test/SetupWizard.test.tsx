import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SetupWizard from '../components/SetupWizard';

// Mock fetch
global.fetch = vi.fn();

describe('SetupWizard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders installation form', () => {
    render(<SetupWizard onSuccess={() => {}} />);
    expect(screen.getByPlaceholderText(/اسم الكلية/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/الادمن/i)).toBeInTheDocument();
    expect(screen.getByText(/الشعار/i)).toBeInTheDocument();
  });

  it('handles form submission successfully', async () => {
    const onSuccessMock = vi.fn();
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ 
        status: 'success', 
        generated_credentials: { username: 'admin', password: 'password123' } 
      }),
    });

    render(<SetupWizard onSuccess={onSuccessMock} />);
    
    fireEvent.change(screen.getByPlaceholderText(/اسم الكلية/i), {
      target: { value: 'Test University' },
    });
    fireEvent.change(screen.getByPlaceholderText(/الادمن/i), {
      target: { value: 'superadmin' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /حفظ/i }));

    await waitFor(() => {
      expect(screen.getByText(/تم الإعداد بنجاح/i)).toBeInTheDocument();
      expect(screen.getByText(/admin/i)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /الذهاب لتسجيل الدخول/i }));
    expect(onSuccessMock).toHaveBeenCalled();
  });
});
