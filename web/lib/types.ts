export interface SelectorTarget {
  testId?: string;
  role?: string;
  text?: string;
  label?: string;
  placeholder?: string;
  css?: string;
  xpath?: string;
}

export interface StepIntent {
  id: string;
  order: number;
  type: string;
  intent: string;
  target?: SelectorTarget;
  value?: string;
  url?: string;
}

export interface AssertionIntent {
  id: string;
  afterStep: string;
  type: 'visible' | 'hidden' | 'url' | 'text' | 'count' | 'enabled' | 'checked';
  target?: SelectorTarget;
  expected?: string;
}

export interface TestIntentConfig {
  timeout: number;
  retries: number;
  viewport: { width: number; height: number };
  browsers: string[];
}

export interface TestIntent {
  id: string;
  name: string;
  description?: string;
  baseUrl: string;
  tags: string[];
  auth?: {
    taskId: string;
  };
  steps: StepIntent[];
  assertions: AssertionIntent[];
  config: TestIntentConfig;
  metadata?: {
    createdAt?: string;
    lastRunAt?: string;
    lastRunStatus?: string;
  };
}

export interface EnvironmentConfig {
  name: string;
  baseUrl: string;
}

export type SuiteRunMode = 'fail-fast' | 'continue';

export interface Suite {
  id: string;
  name: string;
  description?: string;
  intentIds: string[];
  tags: string[];
  isPreset: boolean;
  runMode: SuiteRunMode;
  metadata: {
    createdAt: string;
    updatedAt: string;
    lastRun?: string | null;
    runCount: number;
    passCount: number;
  };
}

export interface BrowserEvent {
  type: string;
  message: string;
  url: string;
  stepId?: string;
  timestamp: string;
  meta?: Record<string, unknown>;
}

export interface StepResult {
  stepId: string;
  intent: string;
  status: 'passed' | 'failed' | 'healed' | 'skipped';
  tier: 'cached' | 'smart-selector' | 'ai-resolver';
  strategy: string;
  confidence: number;
  durationMs: number;
  error?: string;
  screenshot?: string;
  healedFrom?: string;
  healedTo?: string;
  browserEvents?: BrowserEvent[];
}

export interface RunResult {
  testId: string;
  testName: string;
  passed: boolean;
  steps: StepResult[];
  totalDuration: number;
  browser: string;
  timestamp: string;
  healedCount: number;
  environment: {
    baseUrl: string;
    viewport: { width: number; height: number };
    userAgent?: string;
  };
  browserEvents?: BrowserEvent[];
}

export interface JsonReport {
  version: string;
  generatedAt: string;
  result: RunResult;
  metadata: {
    runner: string;
    nodeVersion: string;
  };
}

export interface PageRecord {
  path: string;
  title: string | null;
  last_seen: string;
  visit_count: number;
}

export interface ComponentRecord {
  id?: number;
  page_path: string;
  tag: string;
  role: string | null;
  test_id: string | null;
  text: string | null;
  label: string | null;
  type: string | null;
  placeholder: string | null;
  last_seen: string;
}

export interface NavigationRecord {
  from_path: string;
  to_path: string;
  trigger: string;
  last_seen: string;
}

export interface ApiEndpointRecord {
  method: string;
  url_pattern: string;
  last_status: number | null;
  last_seen: string;
}

export interface KnowledgebaseStats {
  pageCount: number;
  componentCount: number;
  navigationCount: number;
  apiEndpointCount: number;
}
