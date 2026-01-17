'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { jobsApi, type Job, type JobResult } from '@/lib/api';

const statusColors: Record<string, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  processing: 'bg-blue-100 text-blue-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { token } = useAuth();
  const jobId = params.id as string;

  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<JobResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMoreResults, setHasMoreResults] = useState(false);
  const [resultsOffset, setResultsOffset] = useState(0);
  const [isCancelling, setIsCancelling] = useState(false);

  const fetchJob = useCallback(async () => {
    if (!token || !jobId) return;

    try {
      const data = await jobsApi.get(token, jobId);
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job');
    } finally {
      setIsLoading(false);
    }
  }, [token, jobId]);

  const fetchResults = useCallback(
    async (offset = 0, append = false) => {
      if (!token || !jobId) return;

      setIsLoadingResults(true);
      try {
        const data = await jobsApi.getResults(token, jobId, offset, 50);
        if (append) {
          setResults((prev) => [...prev, ...data.results]);
        } else {
          setResults(data.results);
        }
        setHasMoreResults(data.has_more);
        setResultsOffset(offset + data.results.length);
      } catch (err) {
        console.error('Failed to load results:', err);
      } finally {
        setIsLoadingResults(false);
      }
    },
    [token, jobId]
  );

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  useEffect(() => {
    if (job && (job.status === 'completed' || job.status === 'processing')) {
      fetchResults(0);
    }
  }, [job, fetchResults]);

  // Poll for updates while processing
  useEffect(() => {
    if (job?.status === 'pending' || job?.status === 'processing') {
      const interval = setInterval(() => {
        fetchJob();
        if (job?.status === 'processing') {
          fetchResults(0);
        }
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [job?.status, fetchJob, fetchResults]);

  const handleCancel = async () => {
    if (!token || !jobId || isCancelling) return;

    setIsCancelling(true);
    try {
      await jobsApi.cancel(token, jobId);
      await fetchJob();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel job');
    } finally {
      setIsCancelling(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !jobId) return;

    if (!confirm('Are you sure you want to delete this job? This action cannot be undone.')) {
      return;
    }

    try {
      await jobsApi.delete(token, jobId);
      router.push('/jobs');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete job');
    }
  };

  const handleDownload = async () => {
    if (!token || !jobId) return;

    try {
      const { download_url } = await jobsApi.getDownloadUrl(token, jobId);
      window.open(download_url, '_blank');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get download URL');
    }
  };

  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="text-center py-12">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded inline-block">
          {error}
        </div>
        <div className="mt-4">
          <Link href="/jobs" className="text-primary-600 hover:text-primary-500">
            Back to Jobs
          </Link>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const progress =
    job.total_units && job.total_units > 0
      ? Math.round(((job.processed_units || 0) / job.total_units) * 100)
      : 0;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="flex items-center mb-1">
            <Link href="/jobs" className="text-gray-500 hover:text-gray-700 mr-2">
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
            <h1 className="text-2xl font-bold text-gray-900">{job.id}</h1>
          </div>
          <div className="flex items-center space-x-3">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                statusColors[job.status] || 'bg-gray-100 text-gray-800'
              }`}
            >
              {job.status}
            </span>
            <span className="text-sm text-gray-500">Created {formatDate(job.created_at)}</span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {(job.status === 'pending' || job.status === 'processing') && (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50 disabled:opacity-50"
            >
              {isCancelling ? 'Cancelling...' : 'Cancel'}
            </button>
          )}
          {job.status === 'completed' && (
            <button
              onClick={handleDownload}
              className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700"
            >
              Download Results
            </button>
          )}
          <button
            onClick={handleDelete}
            className="px-4 py-2 border border-red-300 text-red-700 text-sm font-medium rounded-md hover:bg-red-50"
          >
            Delete
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Progress bar for processing jobs */}
      {(job.status === 'pending' || job.status === 'processing') && job.total_units && (
        <div className="mb-6 bg-white shadow-sm rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-700">Progress</span>
            <span className="text-sm text-gray-500">
              {job.processed_units || 0} / {job.total_units} ({progress}%)
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          {job.status === 'processing' && (
            <p className="mt-2 text-xs text-gray-500 flex items-center">
              <svg className="animate-spin h-3 w-3 mr-1 text-primary-600" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Processing... Auto-refreshing every 5 seconds
            </p>
          )}
        </div>
      )}

      {/* Job details */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Model</h3>
          <p className="text-sm text-gray-900">{job.model}</p>
        </div>
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Total Units</h3>
          <p className="text-sm text-gray-900">{job.total_units || 'Pending'}</p>
        </div>
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-4">
          <h3 className="text-sm font-medium text-gray-500 mb-2">Failed</h3>
          <p className="text-sm text-gray-900">{job.failed_units || 0}</p>
        </div>
      </div>

      {/* Prompt */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-4 mb-6">
        <h3 className="text-sm font-medium text-gray-500 mb-2">Prompt Template</h3>
        <pre className="text-sm text-gray-900 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded">
          {job.prompt}
        </pre>
      </div>

      {/* Error message for failed jobs */}
      {job.status === 'failed' && job.error_message && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-red-800 mb-2">Error</h3>
          <pre className="text-sm text-red-700 whitespace-pre-wrap font-mono">
            {job.error_message}
          </pre>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-white shadow-sm rounded-lg border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-900">
              Results ({job.processed_units || results.length})
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                    #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Input
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Output
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {results.map((result, index) => (
                  <tr key={result.id || index} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500">{index + 1}</td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900 max-w-xs truncate">
                        {typeof result.input === 'object'
                          ? JSON.stringify(result.input).slice(0, 100)
                          : String(result.input).slice(0, 100)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm text-gray-900 max-w-md">
                        {result.error ? (
                          <span className="text-red-600">{result.error}</span>
                        ) : (
                          <span className="whitespace-pre-wrap">
                            {typeof result.output === 'object'
                              ? JSON.stringify(result.output, null, 2)
                              : String(result.output || '').slice(0, 500)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {result.error ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          Failed
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          Success
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMoreResults && (
            <div className="px-4 py-3 border-t border-gray-200">
              <button
                onClick={() => fetchResults(resultsOffset, true)}
                disabled={isLoadingResults}
                className="text-sm text-primary-600 hover:text-primary-500 disabled:opacity-50"
              >
                {isLoadingResults ? 'Loading...' : 'Load more results'}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
