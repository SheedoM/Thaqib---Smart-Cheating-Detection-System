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

  it('calls success callback on valid cookie session login', async () => {
    const onLoginSuccess = vi.fn();
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ token_type: 'cookie', csrf_token: 'csrf-token' }),
    });

    render(<LoginPage onLoginSuccess={onLoginSuccess} />);
    
    fireEvent.change(screen.getByPlaceholderText(/بريد الكتروني أو اسم المستخدم/i), {
      target: { value: 'admin' },
    });
    fireEvent.change(screen.getByPlaceholderText(/كلمة المرور/i), {
      target: { value: 'password' },
    });
    
    fireEvent.click(screen.getByRole('button', { name: /تسجيل الدخول/i }));

    await waitFor(() => {
      expect(onLoginSuccess).toHaveBeenCalledTimes(1);
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/login'),
        expect.objectContaining({ credentials: 'include' }),
      );
    });
  });
});
