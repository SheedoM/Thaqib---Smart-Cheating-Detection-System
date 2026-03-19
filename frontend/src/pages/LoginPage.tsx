import React, { useState } from 'react';
import { User, Lock, ArrowRight, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api/axios';

export default function LoginPage() {
  const [credentials, setCredentials] = useState({ username: '', password: '' });
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCredentials({ ...credentials, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const params = new URLSearchParams();
      params.append('username', credentials.username);
      params.append('password', credentials.password);

      const response = await api.post('/api/auth/login', params, {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      });

      const { access_token, refresh_token } = response.data;
      login(access_token, refresh_token);
      navigate('/dashboard');
    } catch (err: any) {
      if (err.response?.status === 401) {
        setError('اسم المستخدم أو كلمة المرور غير صحيحة');
      } else {
        setError('حدث خطأ أثناء محاولة تسجيل الدخول. حاول مرة أخرى.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen w-full font-ibm-plex bg-gray-50" dir="rtl">
      {/* Left Form Panel */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center items-center p-8 bg-white shadow-xl z-10">
        <div className="w-full max-w-md space-y-8">
          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold text-gray-900 tracking-tight">تسجيل الدخول</h1>
            <p className="text-gray-500">مرحباً بك مجدداً في نظام ثاقب</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg text-sm font-medium animate-in fade-in slide-in-from-top-2 duration-300">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div className="relative group">
                <User className="absolute right-3 top-3.5 text-gray-400 group-focus-within:text-thaqib-primary transition-colors" size={20} />
                <input
                  type="text"
                  name="username"
                  placeholder="اسم المستخدم"
                  value={credentials.username}
                  onChange={handleInputChange}
                  className="input-field pr-10 focus:ring-thaqib-primary focus:border-thaqib-primary"
                  required
                />
              </div>

              <div className="relative group">
                <Lock className="absolute right-3 top-3.5 text-gray-400 group-focus-within:text-thaqib-primary transition-colors" size={20} />
                <input
                  type="password"
                  name="password"
                  placeholder="كلمة المرور"
                  value={credentials.password}
                  onChange={handleInputChange}
                  className="input-field pr-10 focus:ring-thaqib-primary focus:border-thaqib-primary"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary flex items-center justify-center gap-2 py-3.5 text-lg font-bold shadow-lg shadow-thaqib-primary/20 hover:shadow-xl hover:-translate-y-0.5"
            >
              {isLoading ? (
                <Loader2 className="animate-spin" size={20} />
              ) : (
                <>
                  <span>دخول</span>
                  <ArrowRight size={20} className="rotate-180" />
                </>
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500">
            هل تواجه مشكلة في الدخول؟ <a href="#" className="text-thaqib-primary font-bold hover:underline">اتصل بالدعم الفني</a>
          </p>
        </div>
      </div>

      {/* Right Branding Panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-thaqib-primary relative overflow-hidden flex-col justify-center items-center text-white p-12">
        {/* Decorative elements */}
        <div className="absolute inset-0 opacity-10 pointer-events-none">
          <svg className="absolute w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <path d="M0,50 Q25,20 50,50 T100,50 L100,100 L0,100 Z" fill="currentColor" />
            <path d="M0,60 Q35,80 70,40 T100,60 L100,100 L0,100 Z" fill="currentColor" opacity="0.5" />
          </svg>
        </div>

        <div className="z-10 flex flex-col items-center max-w-md text-center space-y-8 animate-in fade-in zoom-in-95 duration-1000">
          <img src="/thaqib-logo.png" alt="Thaqib Logo" className="w-auto h-48 object-contain drop-shadow-2xl" />
          <div className="space-y-4">
            <h2 className="text-4xl font-bold">ثاقب</h2>
            <p className="text-white/80 text-lg leading-relaxed font-light">
              رؤية ذكية لضمان نزاهة الامتحانات. حماية النزاهة الأكاديمية وتعزيز العدالة من خلال تقنيات الذكاء الاصطناعي المتقدمة.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
