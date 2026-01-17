'use client';

import { useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { filesApi, jobsApi, apiKeysApi, modelsApi, DEFAULT_SYSTEM_PROMPT, type StoredAPIKey, type OpenRouterModel } from '@/lib/api';

type Step = 'upload' | 'prompt' | 'settings' | 'review';

interface FileInfo {
  id: string;
  key: string;
  name: string;
  size: number;
  row_count: number;
  columns: string[];
  preview_rows: Record<string, unknown>[];
  file_type: string;
}

export default function NewJobPage() {
  const router = useRouter();
  const { token, user } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step tracking
  const [currentStep, setCurrentStep] = useState<Step>('upload');

  // Step 1: File upload
  const [_file, setFile] = useState<File | null>(null);
  const [fileInfo, setFileInfo] = useState<FileInfo | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);

  // Step 2: Prompt
  const [prompt, setPrompt] = useState('');

  // Step 3: Settings
  const [models, setModels] = useState<OpenRouterModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelSearch, setModelSearch] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [apiKeys, setApiKeys] = useState<StoredAPIKey[]>([]);
  const [selectedApiKeyId, setSelectedApiKeyId] = useState<string>('');
  const [batchSize, setBatchSize] = useState(10);
  const [maxTokens, setMaxTokens] = useState(1000);
  const [outputFormat, setOutputFormat] = useState<'enriched' | 'separate'>('enriched');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);

  // Submission
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (!selectedFile || !token) return;

      setFile(selectedFile);
      setIsUploading(true);
      setError(null);

      try {
        // Get presigned upload URL
        const uploadResponse = await filesApi.requestUpload(
          token,
          selectedFile.name,
          selectedFile.type || 'text/csv'
        );
        console.log('Upload response from API:', uploadResponse);

        // Upload file directly to S3 using presigned POST
        await filesApi.uploadToS3(uploadResponse.upload_url, uploadResponse.fields, selectedFile);
        setUploadProgress(100);

        // Confirm upload and get file info with metadata
        const info = await filesApi.confirmUpload(token, uploadResponse.file_id, uploadResponse.key);
        setFileInfo({
          id: uploadResponse.file_id,
          key: uploadResponse.key,
          name: selectedFile.name,
          size: selectedFile.size,
          row_count: info.row_count || 0,
          columns: info.columns || [],
          preview_rows: info.preview_rows || [],
          file_type: info.file_type || 'unknown',
        });
      } catch (err) {
        console.error('File upload error:', err);
        setError(err instanceof Error ? err.message : 'Upload failed');
        setFile(null);
      } finally {
        setIsUploading(false);
        setUploadProgress(0);
      }
    },
    [token]
  );

  const loadApiKeys = useCallback(async () => {
    if (!token) return;
    try {
      const keys = await apiKeysApi.list(token);
      setApiKeys(keys);
      // Only auto-select first key if user doesn't have platform key access
      if (keys.length > 0 && !selectedApiKeyId && !user?.can_use_platform_key) {
        setSelectedApiKeyId(keys[0].id);
      }
    } catch (err) {
      console.error('Failed to load API keys:', err);
    }
  }, [token, selectedApiKeyId, user?.can_use_platform_key]);

  const loadModels = useCallback(async () => {
    if (models.length > 0) return; // Already loaded
    setModelsLoading(true);
    try {
      const fetchedModels = await modelsApi.list();
      setModels(fetchedModels);
      // Select first model if none selected
      if (!selectedModel && fetchedModels.length > 0) {
        setSelectedModel(fetchedModels[0].id);
      }
    } catch (err) {
      console.error('Failed to load models:', err);
    } finally {
      setModelsLoading(false);
    }
  }, [models.length, selectedModel]);

  const goToStep = (step: Step) => {
    if (step === 'settings') {
      loadApiKeys();
      loadModels();
    }
    setCurrentStep(step);
  };

  const insertPlaceholder = (column: string) => {
    setPrompt((prev) => prev + `{${column}}`);
  };

  const handleSubmit = async () => {
    if (!token || !fileInfo) return;

    setIsSubmitting(true);
    setError(null);

    try {
      // Only include custom system prompt if modified from default
      const customSystemPrompt = systemPrompt !== DEFAULT_SYSTEM_PROMPT ? systemPrompt : undefined;

      const job = await jobsApi.create(token, {
        input_file_key: fileInfo.key,
        prompt,
        model: selectedModel,
        api_key_id: selectedApiKeyId || undefined,
        config: {
          batch_size: batchSize,
          max_tokens: maxTokens,
          output_format: outputFormat,
          system_prompt: customSystemPrompt,
        },
      });

      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create job');
      setIsSubmitting(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const steps = [
    { id: 'upload', name: 'Upload File' },
    { id: 'prompt', name: 'Configure Prompt' },
    { id: 'settings', name: 'Settings' },
    { id: 'review', name: 'Review' },
  ];

  const currentStepIndex = steps.findIndex((s) => s.id === currentStep);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Create New Job</h1>
        <p className="mt-1 text-sm text-gray-500">
          Upload a file and configure your batch processing job
        </p>
      </div>

      {/* Progress steps */}
      <nav className="mb-8">
        <ol className="flex items-center">
          {steps.map((step, index) => (
            <li key={step.id} className="relative flex-1">
              <div className="relative z-10 flex items-center">
                <span
                  className={`w-8 h-8 flex items-center justify-center rounded-full text-sm font-medium ${
                    index < currentStepIndex
                      ? 'bg-primary-600 text-white'
                      : index === currentStepIndex
                      ? 'bg-primary-600 text-white'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {index < currentStepIndex ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                      <path
                        fillRule="evenodd"
                        d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    index + 1
                  )}
                </span>
                <span
                  className={`ml-2 text-sm font-medium bg-white pr-2 ${
                    index <= currentStepIndex ? 'text-gray-900' : 'text-gray-500'
                  }`}
                >
                  {step.name}
                </span>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={`absolute top-4 left-8 w-full h-0.5 ${
                    index < currentStepIndex ? 'bg-primary-600' : 'bg-gray-200'
                  }`}
                  style={{ marginLeft: '1rem', width: 'calc(100% - 3rem)' }}
                />
              )}
            </li>
          ))}
        </ol>
      </nav>

      {/* Error display */}
      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Step content */}
      <div className="bg-white shadow-sm rounded-lg border border-gray-200 p-6">
        {/* Step 1: Upload */}
        {currentStep === 'upload' && (
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">Upload Your Data File</h2>
            <p className="text-sm text-gray-500 mb-6">
              Upload a CSV or JSON file containing the data you want to process.
            </p>

            {!fileInfo ? (
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center ${
                  isUploading ? 'border-primary-300 bg-primary-50' : 'border-gray-300'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.json,.jsonl"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                {isUploading ? (
                  <div>
                    <div className="w-16 h-16 mx-auto mb-4">
                      <svg className="animate-spin h-16 w-16 text-primary-600" viewBox="0 0 24 24">
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
                    </div>
                    <p className="text-sm text-gray-500">Uploading... {uploadProgress}%</p>
                  </div>
                ) : (
                  <>
                    <svg
                      className="mx-auto h-12 w-12 text-gray-400"
                      stroke="currentColor"
                      fill="none"
                      viewBox="0 0 48 48"
                    >
                      <path
                        d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                    <div className="mt-4">
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700"
                      >
                        Select File
                      </button>
                    </div>
                    <p className="mt-2 text-xs text-gray-500">CSV, JSON, or JSONL up to 100MB</p>
                  </>
                )}
              </div>
            ) : (
              <div className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <svg
                      className="h-8 w-8 text-gray-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                    <div className="ml-3">
                      <p className="text-sm font-medium text-gray-900">{fileInfo.name}</p>
                      <p className="text-xs text-gray-500">
                        {formatFileSize(fileInfo.size)} • {fileInfo.row_count} rows •{' '}
                        {fileInfo.columns.length} columns
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setFile(null);  // Reset file state
                      setFileInfo(null);
                    }}
                    className="text-gray-400 hover:text-gray-500"
                  >
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                </div>
                <div className="mt-3">
                  <p className="text-xs font-medium text-gray-500 mb-1">Columns:</p>
                  <div className="flex flex-wrap gap-1">
                    {fileInfo.columns.map((col) => (
                      <span
                        key={col}
                        className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700"
                      >
                        {col}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Preview table */}
                {fileInfo.preview_rows.length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs font-medium text-gray-500 mb-2">Preview (first {fileInfo.preview_rows.length} rows):</p>
                    <div className="overflow-x-auto border border-gray-200 rounded">
                      <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                          <tr>
                            {fileInfo.columns.map((col) => (
                              <th
                                key={col}
                                className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                              >
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                          {fileInfo.preview_rows.map((row, idx) => (
                            <tr key={idx}>
                              {fileInfo.columns.map((col) => (
                                <td key={col} className="px-3 py-2 text-xs text-gray-900 truncate max-w-xs">
                                  {String(row[col] ?? '')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => goToStep('prompt')}
                disabled={!fileInfo}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Prompt */}
        {currentStep === 'prompt' && fileInfo && (
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">Configure Your Prompt</h2>
            <p className="text-sm text-gray-500 mb-6">
              Write a prompt template. Use {'{column_name}'} placeholders to insert data from each
              row.
            </p>

            <div className="mb-4">
              <p className="text-xs font-medium text-gray-500 mb-2">
                Click to insert column placeholders:
              </p>
              <div className="flex flex-wrap gap-1">
                {fileInfo.columns.map((col) => (
                  <button
                    key={col}
                    type="button"
                    onClick={() => insertPlaceholder(col)}
                    className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-primary-50 text-primary-700 hover:bg-primary-100"
                  >
                    {'{'}
                    {col}
                    {'}'}
                  </button>
                ))}
              </div>
            </div>

            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
              placeholder={`Example: Translate the following text to Spanish:\n\n{${fileInfo.columns[0] || 'text'}}`}
            />

            <div className="mt-6 flex justify-between">
              <button
                type="button"
                onClick={() => goToStep('upload')}
                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
              >
                Back
              </button>
              <button
                type="button"
                onClick={() => goToStep('settings')}
                disabled={!prompt.trim()}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Settings */}
        {currentStep === 'settings' && (
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">Processing Settings</h2>

            <div className="space-y-6">
              {/* Model selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Model
                  {modelsLoading && (
                    <span className="ml-2 text-xs text-gray-400">(loading...)</span>
                  )}
                </label>
                <input
                  type="text"
                  placeholder="Search models..."
                  value={modelSearch}
                  onChange={(e) => setModelSearch(e.target.value)}
                  className="w-full px-3 py-2 mb-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
                <div className="max-h-64 overflow-y-auto border border-gray-300 rounded-md">
                  {modelsLoading ? (
                    <div className="px-3 py-8 text-sm text-gray-500 text-center">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600 mx-auto mb-2"></div>
                      Loading models from OpenRouter...
                    </div>
                  ) : models.length === 0 ? (
                    <div className="px-3 py-4 text-sm text-gray-500 text-center">
                      Failed to load models. Please refresh the page.
                    </div>
                  ) : (
                    <>
                      {models
                        .filter(m =>
                          modelSearch === '' ||
                          m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
                          m.id.toLowerCase().includes(modelSearch.toLowerCase())
                        )
                        .slice(0, 100)
                        .map((model) => {
                          const isSelected = model.id === selectedModel;
                          const pricePerMillion = (parseFloat(model.pricing.prompt) * 1000000).toFixed(2);
                          return (
                            <div
                              key={model.id}
                              onClick={() => setSelectedModel(model.id)}
                              className={`px-3 py-2 cursor-pointer border-b border-gray-100 last:border-b-0 ${
                                isSelected
                                  ? 'bg-primary-50 border-l-2 border-l-primary-500'
                                  : 'hover:bg-gray-50'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className={`text-sm font-medium ${isSelected ? 'text-primary-700' : 'text-gray-900'}`}>
                                  {model.name}
                                </span>
                                <span className="text-xs text-gray-500">
                                  ${pricePerMillion}/M tokens
                                </span>
                              </div>
                              <div className="text-xs text-gray-500 truncate">
                                {model.id}
                                {model.context_length && ` • ${(model.context_length / 1000).toFixed(0)}K context`}
                              </div>
                            </div>
                          );
                        })}
                      {models.filter(m =>
                        modelSearch === '' ||
                        m.name.toLowerCase().includes(modelSearch.toLowerCase()) ||
                        m.id.toLowerCase().includes(modelSearch.toLowerCase())
                      ).length === 0 && (
                        <div className="px-3 py-4 text-sm text-gray-500 text-center">
                          No models found matching "{modelSearch}"
                        </div>
                      )}
                    </>
                  )}
                </div>
                {selectedModel && (
                  <div className="mt-2 text-xs text-gray-500">
                    Selected: <span className="font-medium">{models.find(m => m.id === selectedModel)?.name || selectedModel}</span>
                  </div>
                )}
              </div>

              {/* API Key selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">API Key</label>
                {apiKeys.length === 0 ? (
                  user?.can_use_platform_key ? (
                    <div className="flex items-center text-sm text-gray-700">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 mr-2">
                        Platform Key
                      </span>
                      You have access to use the platform API key
                    </div>
                  ) : (
                    <div className="text-sm text-gray-500">
                      No API keys configured.{' '}
                      <a href="/settings/api-keys" className="text-primary-600 hover:text-primary-500">
                        Add one in settings
                      </a>
                    </div>
                  )
                ) : (
                  <select
                    value={selectedApiKeyId}
                    onChange={(e) => setSelectedApiKeyId(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                  >
                    {user?.can_use_platform_key && (
                      <option value="">Use Platform Key</option>
                    )}
                    {apiKeys.map((key) => (
                      <option key={key.id} value={key.id}>
                        {key.name || key.provider} ({key.masked_key})
                      </option>
                    ))}
                  </select>
                )}
              </div>

              {/* Batch size */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Batch Size
                  <span className="ml-1 text-gray-400 font-normal">(concurrent requests)</span>
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  value={batchSize}
                  onChange={(e) => setBatchSize(parseInt(e.target.value) || 10)}
                  className="w-32 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              {/* Max tokens */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Tokens
                  <span className="ml-1 text-gray-400 font-normal">(per response)</span>
                </label>
                <input
                  type="number"
                  min={1}
                  max={4096}
                  value={maxTokens}
                  onChange={(e) => setMaxTokens(parseInt(e.target.value) || 1000)}
                  className="w-32 px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500"
                />
              </div>

              {/* Output format */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Output Format
                </label>
                <div className="space-y-2">
                  <label className="flex items-start">
                    <input
                      type="radio"
                      name="outputFormat"
                      value="enriched"
                      checked={outputFormat === 'enriched'}
                      onChange={() => setOutputFormat('enriched')}
                      className="mt-1 h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300"
                    />
                    <span className="ml-3">
                      <span className="block text-sm text-gray-900">Enriched</span>
                      <span className="block text-xs text-gray-500">Original data + AI-generated fields combined</span>
                    </span>
                  </label>
                  <label className="flex items-start">
                    <input
                      type="radio"
                      name="outputFormat"
                      value="separate"
                      checked={outputFormat === 'separate'}
                      onChange={() => setOutputFormat('separate')}
                      className="mt-1 h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300"
                    />
                    <span className="ml-3">
                      <span className="block text-sm text-gray-900">Separate</span>
                      <span className="block text-xs text-gray-500">AI-generated results only (without original data)</span>
                    </span>
                  </label>
                </div>
              </div>
            </div>

            {/* Advanced Settings */}
            <div className="border-t border-gray-200 pt-6 mt-6">
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                <svg
                  className={`mr-2 h-4 w-4 transform transition-transform ${showAdvanced ? 'rotate-90' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Advanced Settings
              </button>

              {showAdvanced && (
                <div className="mt-4 space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      System Prompt
                    </label>
                    <p className="text-xs text-gray-500 mb-2">
                      Instructions given to the AI model before your prompt. The default ensures JSON output.
                    </p>
                    <textarea
                      value={systemPrompt}
                      onChange={(e) => setSystemPrompt(e.target.value)}
                      rows={8}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm font-mono focus:ring-primary-500 focus:border-primary-500"
                      placeholder="Enter system prompt..."
                    />
                    {systemPrompt !== DEFAULT_SYSTEM_PROMPT && (
                      <button
                        type="button"
                        onClick={() => setSystemPrompt(DEFAULT_SYSTEM_PROMPT)}
                        className="mt-2 text-xs text-primary-600 hover:text-primary-700"
                      >
                        Reset to default
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-between">
              <button
                type="button"
                onClick={() => goToStep('prompt')}
                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
              >
                Back
              </button>
              <button
                type="button"
                onClick={() => goToStep('review')}
                disabled={!selectedModel || (apiKeys.length === 0 && !user?.can_use_platform_key)}
                className="px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </div>
        )}

        {/* Step 4: Review */}
        {currentStep === 'review' && fileInfo && (
          <div>
            <h2 className="text-lg font-medium text-gray-900 mb-4">Review Your Job</h2>

            <div className="space-y-4">
              <div className="border border-gray-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">File</h3>
                <p className="text-sm text-gray-900">{fileInfo.name}</p>
                <p className="text-xs text-gray-500">
                  {fileInfo.row_count} rows • {fileInfo.columns.length} columns
                </p>
              </div>

              <div className="border border-gray-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Prompt</h3>
                <pre className="text-sm text-gray-900 whitespace-pre-wrap font-mono bg-gray-50 p-2 rounded">
                  {prompt}
                </pre>
              </div>

              <div className="border border-gray-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Settings</h3>
                <dl className="grid grid-cols-2 gap-4">
                  <div>
                    <dt className="text-xs text-gray-500">Model</dt>
                    <dd className="text-sm text-gray-900">
                      {models.find((m) => m.id === selectedModel)?.name || selectedModel}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">API Key</dt>
                    <dd className="text-sm text-gray-900">
                      {selectedApiKeyId
                        ? apiKeys.find((k) => k.id === selectedApiKeyId)?.name || 'Selected'
                        : user?.can_use_platform_key
                        ? <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-800">Platform Key</span>
                        : 'None'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">Batch Size</dt>
                    <dd className="text-sm text-gray-900">{batchSize}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">Max Tokens</dt>
                    <dd className="text-sm text-gray-900">{maxTokens}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">Output Format</dt>
                    <dd className="text-sm text-gray-900 capitalize">{outputFormat}</dd>
                  </div>
                  {systemPrompt !== DEFAULT_SYSTEM_PROMPT && (
                    <div className="col-span-2">
                      <dt className="text-xs text-gray-500">System Prompt</dt>
                      <dd className="text-sm text-gray-900">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                          Custom
                        </span>
                      </dd>
                    </div>
                  )}
                </dl>
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <div className="flex">
                  <svg
                    className="h-5 w-5 text-yellow-400"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                  >
                    <path
                      fillRule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-yellow-800">Cost Estimate</h3>
                    <p className="mt-1 text-sm text-yellow-700">
                      Processing {fileInfo.row_count} rows will use approximately{' '}
                      {fileInfo.row_count * maxTokens} tokens. Actual costs depend on your prompt
                      and response lengths.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-between">
              <button
                type="button"
                onClick={() => goToStep('settings')}
                className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-md hover:bg-gray-50"
              >
                Back
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={isSubmitting}
                className="px-6 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 disabled:opacity-50"
              >
                {isSubmitting ? 'Creating Job...' : 'Create Job'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
