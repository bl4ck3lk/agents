'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { usageApi, type UsageSummary, type UsageRecord } from '@/lib/api';

function formatCost(cost: number | string): string {
  const num = typeof cost === 'string' ? parseFloat(cost) : cost;
  return `$${num.toFixed(4)}`;
}

function formatTokens(tokens: number): string {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(1)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}K`;
  }
  return tokens.toString();
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function UsagePage() {
  const { token } = useAuth();
  const [summary, setSummary] = useState<UsageSummary | null>(null);
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  useEffect(() => {
    const fetchData = async () => {
      if (!token) return;

      setIsLoading(true);
      setError(null);

      try {
        const [summaryData, recordsData] = await Promise.all([
          usageApi.getSummary(token, days),
          usageApi.list(token, { limit: 50 }),
        ]);
        setSummary(summaryData);
        setRecords(recordsData.records);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load usage data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
  }, [token, days]);

  const handleExport = async () => {
    if (!token) return;
    try {
      const blob = await usageApi.exportCsv(token);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'usage_export.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Failed to export data');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Usage</h1>
          <p className="mt-1 text-sm text-gray-500">
            Track your token usage and costs
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-primary-500 focus:border-primary-500"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={handleExport}
            className="px-4 py-2 bg-white border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
          >
            Export CSV
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : summary ? (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-500">Total Cost</p>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                {formatCost(summary.total_cost_usd)}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                Raw: {formatCost(summary.total_raw_cost_usd)} + Markup: {formatCost(summary.total_markup_usd)}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-500">Total Tokens</p>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                {formatTokens(summary.total_tokens_input + summary.total_tokens_output)}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                Input: {formatTokens(summary.total_tokens_input)} / Output: {formatTokens(summary.total_tokens_output)}
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-500">Jobs Processed</p>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                {summary.total_jobs}
              </p>
              <p className="mt-1 text-xs text-gray-500">
                {summary.platform_key_jobs} using platform key
              </p>
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <p className="text-sm font-medium text-gray-500">Avg Cost/Job</p>
              <p className="mt-2 text-3xl font-bold text-gray-900">
                {summary.total_jobs > 0
                  ? formatCost(summary.total_cost_usd / summary.total_jobs)
                  : '$0.00'}
              </p>
            </div>
          </div>

          {/* Model Breakdown */}
          {summary.by_model.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6 mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage by Model</h2>
              <div className="space-y-3">
                {summary.by_model.map((model) => (
                  <div key={model.model} className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900">{model.model}</span>
                        <span className="text-sm text-gray-500">{formatCost(model.cost_usd)}</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-primary-600 h-2 rounded-full"
                          style={{
                            width: `${Math.min(100, (model.cost_usd / summary.total_cost_usd) * 100)}%`,
                          }}
                        ></div>
                      </div>
                      <div className="flex justify-between mt-1 text-xs text-gray-500">
                        <span>{model.count} jobs</span>
                        <span>{formatTokens(model.tokens_input + model.tokens_output)} tokens</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recent Usage Table */}
          <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Recent Usage</h2>
            </div>
            {records.length === 0 ? (
              <div className="px-6 py-8 text-center text-gray-500">
                No usage records yet. Create a job to start tracking usage.
              </div>
            ) : (
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Job
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Model
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Tokens
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Cost
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {records.map((record) => (
                    <tr key={record.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <Link
                          href={`/jobs/${record.job_id}`}
                          className="text-sm font-medium text-primary-600 hover:text-primary-800"
                        >
                          {record.job_id}
                        </Link>
                        {record.used_platform_key && (
                          <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">
                            Platform
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {record.model || 'unknown'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        <span title={`Input: ${record.tokens_input.toLocaleString()}, Output: ${record.tokens_output.toLocaleString()}`}>
                          {formatTokens(record.tokens_input + record.tokens_output)}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatCost(record.cost_usd)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(record.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}
