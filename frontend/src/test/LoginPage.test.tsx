import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LoginPage from '../pages/LoginPage';

// Mock fetch
global.fetch = vi.fn();

describe('LoginPage Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form correctly', () => {
    render(<LoginPage />);
    expect(screen.getByPlaceholderText(/بريد الكتروني أو اسم المستخدم/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/كلمة المرور/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /تسجيل الدخول/i })).toBeInTheDocument();
  });

  it('shows error message on failed login', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: 'Invalid credentials' }),
    });

    render(<LoginPage />);
    
    fireEvent.change(screen.getByPlaceholderText(/بريد الكتروني أو اسم المستخدم/i), {
      target: { value: 'wronguser' },
    });
    fireEvent.change(screen.getByPlaceholderText(/كلمة المرور/i), {
      target: { value: 'wrongpass' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /تسجيل الدخول/i }));

    await waitFor(() => {
      expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument();
    });
  });

  it('shows success alert on valid login', async () => {
    const alertMock = vi.spyOn(window, 'alert').mockImplementation(() => {});
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ access_token: 'fake-token' }),
    });

    render(<LoginPage />);
    
    fireEvent.change(screen.getByPlaceholderText(/بريد الكتروني أو اسم المستخدم/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByPlaceholderText(/كلمة المرور/i), {
      target: { value: 'password' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /تسجيل الدخول/i }));

    await waitFor(() => {
      expect(alertMock).toHaveBeenCalledWith(expect.stringContaining('تم تسجيل الدخول بنجاح'));
    });
  });
});
