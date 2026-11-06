import type { JobInput, Provider } from './types';
export function routeJob(job: JobInput): Provider {
  if (job.compute === 'github') return 'github';
  if (job.compute === 'kaggle') { if (!job.requiresGpu) throw new Error('Kaggle is reserved for GPU production tasks; this job does not require GPU'); return 'kaggle'; }
  if (job.compute && job.compute !== 'automatic') throw new Error('Unsupported compute mode');
  return job.requiresGpu ? 'kaggle' : 'github';
}
