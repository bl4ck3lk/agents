'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { apiKeysApi, type StoredAPIKey } from '@/lib/api';

const PROVIDERS = [
  { id: 'openai', name: 'OpenAI' },
  { id: 'anthropic', name: 'Anthropic' },
  { id: 'openrouter', name: 'OpenRouter' },
];

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
}

function TrashIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
    </svg>
  );
}

export default function ApiKeysPage() {
  const { token } = useAuth();
  const [keys, setKeys] = useState<StoredAPIKey[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add new key form
  const [isAdding, setIsAdding] = useState(false);
  const [provider, setProvider] = useState(PROVIDERS[0].id);
  const [apiKey, setApiKey] = useState('');
  const [keyName, setKeyName] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Deleting
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchKeys = useCallback(async () => {
    if (!token) return;

    setIsLoading(true);
    setError(null);

    try {
      const data = await apiKeysApi.list(token);
      setKeys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load API keys');
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !apiKey.trim()) return;

    setIsSaving(true);
    setError(null);

    try {
      await apiKeysApi.create(token, {
        provider,
        api_key: apiKey,
        name: keyName || undefined,
      });
      setApiKey('');
      setKeyName('');
      setIsAdding(false);
      await fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save API key');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    if (!token) return;

    if (!confirm('Are you sure you want to delete this API key?')) {
      return;
    }

    setDeletingId(keyId);

    try {
      await apiKeysApi.delete(token, keyId);
      await fetchKeys();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete API key');
    } finally {
      setDeletingId(null);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">API Keys</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your LLM provider API keys for batch processing
          </p>
        </div>
        {!isAdding && (
          <button
            onClick={() => setIsAdding(true)}
            className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700"
          >
            <PlusIcon className="mr-2 h-4 w-4" />
            Add Key
          </button>
        )}
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Add key form */}
      {isAdding && (
        <div className="mb-6 bg-white shadow-sm rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">Add New API Key</h3>
          <form onSubmit={handleAddKey} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label htmlFor="provider" className="block text-sm font-medium text-gray-700">
                  Provider
                </label>
                <select
                  id="provider"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                >
                  {PROVIDERS.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="keyName" className="block text-sm font-medium text-gray-700">
                  Name (optional)
                </label>
                <input
                  type="text"
                  id="keyName"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="e.g., Production Key"
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>
            </div>

            <div>
              <label htmlFor="apiKey" className="block text-sm font-medium text-gray-700">
                API Key
              </label>
              <input
                type="password"
                id="apiKey"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                required
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 font-mono"
              />
              <p className="mt-1 text-xs text-gray-500">
                Your API key is encrypted before storage and never exposed after saving.
              </p>
            </div>

            <div className="flex items-center space-x-3">
              <button
                type="submit"
                disabled={isSaving || !apiKey.trim()}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {isSaving ? 'Saving...' : 'Save Key'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsAdding(false);
                  setApiKey('');
                  setKeyName('');
                }}
                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Keys list */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : keys.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1}
              d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No API keys</h3>
          <p className="mt-1 text-sm text-gray-500">
            Add an API key to start processing jobs.
          </p>
          <div className="mt-6">
            <button
              onClick={() => setIsAdding(true)}
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700"
            >
              <PlusIcon className="mr-2 h-4 w-4" />
              Add Key
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Key
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Added
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {keys.map((key) => (
                <tr key={key.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="text-sm font-medium text-gray-900">
                      {key.name || '-'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                      {PROVIDERS.find((p) => p.id === key.provider)?.name || key.provider}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <code className="text-sm text-gray-500 font-mono">{key.masked_key}</code>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(key.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <button
                      onClick={() => handleDeleteKey(key.id)}
                      disabled={deletingId === key.id}
                      className="text-red-600 hover:text-red-900 disabled:opacity-50"
                    >
                      <TrashIcon className="h-5 w-5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Security note */}
      <div className="mt-8 bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex">
          <svg
            className="h-5 w-5 text-blue-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">Security Information</h3>
            <div className="mt-2 text-sm text-blue-700">
              <ul className="list-disc list-inside space-y-1">
                <li>API keys are encrypted at rest using AES-256 encryption</li>
                <li>Keys are only decrypted when needed for processing</li>
                <li>We never log or expose your full API keys</li>
                <li>You can delete keys at any time</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
