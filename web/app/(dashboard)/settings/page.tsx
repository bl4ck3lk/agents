'use client';

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { authApi } from '@/lib/api';

export default function SettingsPage() {
  const { token, user, setUser } = useAuth();
  const [name, setName] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (user?.name) {
      setName(user.name);
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    setIsSaving(true);
    setMessage(null);

    try {
      const updatedUser = await authApi.updateMe(token, { name });
      setUser(updatedUser);
      setMessage({ type: 'success', text: 'Settings saved successfully' });
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save settings',
      });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">Manage your account settings</p>
      </div>

      <div className="bg-white shadow-sm rounded-lg border border-gray-200">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Profile</h3>

          {message && (
            <div
              className={`mb-4 px-4 py-3 rounded ${
                message.type === 'success'
                  ? 'bg-green-50 border border-green-200 text-green-700'
                  : 'bg-red-50 border border-red-200 text-red-700'
              }`}
            >
              {message.text}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                type="email"
                id="email"
                value={user?.email || ''}
                disabled
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm bg-gray-50 text-gray-500"
              />
              <p className="mt-1 text-xs text-gray-500">Email cannot be changed</p>
            </div>

            <div>
              <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                Name
              </label>
              <input
                type="text"
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
              />
            </div>

            <div className="pt-4">
              <button
                type="submit"
                disabled={isSaving}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="mt-8 bg-white shadow-sm rounded-lg border border-gray-200">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Account Status</h3>
          <div className="space-y-2">
            <div className="flex items-center">
              <span className="text-sm text-gray-500 w-32">Status:</span>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  user?.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                }`}
              >
                {user?.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div className="flex items-center">
              <span className="text-sm text-gray-500 w-32">Email verified:</span>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  user?.is_verified ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                }`}
              >
                {user?.is_verified ? 'Verified' : 'Pending'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
