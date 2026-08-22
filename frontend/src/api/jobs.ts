import { apiClient, ApiError, isApiError } from './client';
import type { JobCreateResponse, JobStatus, JobRow, RetryFailedResponse, CreditsResponse } from '../types/api';

export const jobsApi = {
  async createJob(file: File): Promise<JobCreateResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<JobCreateResponse>('/api/jobs', formData);
  },

  async getJobs(): Promise<JobStatus[]> {
    const response = await apiClient.get<{ jobs: JobStatus[] }>('/api/jobs');
    return response.jobs;
  },

  async getJob(jobId: string): Promise<JobStatus> {
    return apiClient.get<JobStatus>(`/api/jobs/${jobId}`);
  },

  async getJobRows(jobId: string): Promise<JobRow[]> {
    return apiClient.get<JobRow[]>(`/api/jobs/${jobId}/rows`);
  },

  async retryFailedRows(jobId: string): Promise<RetryFailedResponse> {
    return apiClient.post<RetryFailedResponse>(`/api/jobs/${jobId}/retry-failed`, {});
  },

  async downloadJob(jobId: string, filename: string): Promise<void> {
    return apiClient.download(`/api/jobs/${jobId}/download`, filename);
  },

  async getCredits(): Promise<CreditsResponse> {
    return apiClient.get<CreditsResponse>('/api/credits');
  },
};

export { ApiError, isApiError };