export interface Env { DB: D1Database; ASSETS: R2Bucket; APP_AUTH_TOKEN: string; ENCRYPTION_KEY: string; GITHUB_TOKEN?: string; GITHUB_OWNER?: string; GITHUB_REPO?: string; WORKER_CALLBACK_TOKEN?: string; TELEGRAM_BOT_TOKEN?: string; TELEGRAM_CHAT_ID?: string; }
export type Provider = 'github'|'kaggle';
export interface JobInput { workflowId?: string; tool: string; compute?: 'automatic'|'github'|'kaggle'; requiresGpu?: boolean; payload: Record<string, unknown>; idempotencyKey?: string; }
