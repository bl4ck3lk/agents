'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { jobsApi, type Job } from '@/lib/api';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
    </svg>
  );
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

export default function JobsPage() {
  const { token } = useAuth();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    const fetchJobs = async () => {
      if (!token) return;

      setIsLoading(true);
      setError(null);

      try {
        const status = statusFilter === 'all' ? undefined : statusFilter;
        const response = await jobsApi.list(token, 0, 50, status);
        setJobs(response.jobs);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load jobs');
      } finally {
        setIsLoading(false);
      }
    };

    fetchJobs();
  }, [token, statusFilter]);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Jobs</h1>
          <p className="mt-1 text-sm text-gray-500">
            Manage your batch processing jobs
          </p>
        </div>
        <Link
          href="/jobs/new"
          className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 transition-colors"
        >
          <PlusIcon className="mr-2 h-4 w-4" />
          New Job
        </Link>
      </div>

      {/* Filters */}
      <div className="mb-6">
        <div className="flex space-x-2">
          {['all', 'pending', 'processing', 'completed', 'failed'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                statusFilter === status
                  ? 'bg-primary-100 text-primary-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Loading state */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      ) : jobs.length === 0 ? (
        /* Empty state */
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
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-gray-900">No jobs</h3>
          <p className="mt-1 text-sm text-gray-500">
            Get started by creating a new job.
          </p>
          <div className="mt-6">
            <Link
              href="/jobs/new"
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700"
            >
              <PlusIcon className="mr-2 h-4 w-4" />
              New Job
            </Link>
          </div>
        </div>
      ) : (
        /* Jobs table */
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Job ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Model
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Progress
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Created
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {jobs.map((job) => (
                <tr key={job.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-sm font-medium text-primary-600 hover:text-primary-800"
                    >
                      {job.id}
                    </Link>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.model}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium w-fit ${
                          statusColors[job.status] || 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {job.status}
                      </span>
                      {job.status === 'failed' && job.error_message && (
                        <span className="mt-1 text-xs text-red-600 max-w-xs truncate" title={job.error_message}>
                          {job.error_message}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {job.total_units ? (
                      <div className="flex items-center">
                        <div className="w-24 bg-gray-200 rounded-full h-2 mr-2">
                          <div
                            className="bg-primary-600 h-2 rounded-full"
                            style={{
                              width: `${Math.round(
                                ((job.processed_units || 0) / job.total_units) * 100
                              )}%`,
                            }}
                          ></div>
                        </div>
                        <span className="text-xs text-gray-500">
                          {job.processed_units || 0}/{job.total_units}
                        </span>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-500">-</span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {formatDate(job.created_at)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <Link
                      href={`/jobs/${job.id}`}
                      className="text-primary-600 hover:text-primary-900"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
