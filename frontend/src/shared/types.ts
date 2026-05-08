export interface Vendor {
  id: number;
  name: string;
}

export interface SystemVersion {
  id: number;
  system_id: number;
  version: string;
}

export interface SystemItem {
  id: number;
  name: string;
  versions?: SystemVersion[];
}

export interface Device {
  id: number;
  model: string;
  status: string;
  type: string | null;
  vendor_id: number;
  vendor_name: string;
  system_id: number;
  system_name: string;
  system_version_id: number;
  system_version: string;
  resolution: string | null;
  arch: string | null;
  cpu: string | null;
  boot_password: string | null;
  notes: string | null;
  loan_status: string;
  borrower_name: string | null;
  borrower_user_id: string | null;
  borrower_open_id: string | null;
  borrower_avatar_url: string | null;
  borrower_job_title: string | null;
  borrowed_at: string | null;
  expected_return_at: string | null;
}

export interface BorrowRequestItem {
  id: number;
  device_id: number;
  device_model: string;
  borrower_name: string;
  borrower_user_id: string | null;
  borrower_open_id: string | null;
  borrower_avatar_url: string | null;
  borrower_job_title: string | null;
  expected_return_at: string;
  request_type: string;
  request_status: string;
  requested_at: string;
  handled_at: string | null;
  device_status: string | null;
  device_type: string | null;
  vendor_name: string | null;
  system_name: string | null;
  system_version: string | null;
  resolution: string | null;
  arch: string | null;
  cpu: string | null;
  boot_password: string | null;
  notes: string | null;
}

export interface BorrowRecord {
  id: number;
  device_id: number;
  device_model: string;
  borrower_name: string;
  borrower_user_id: string | null;
  borrower_open_id: string | null;
  borrower_avatar_url: string | null;
  borrower_job_title: string | null;
  borrowed_at: string;
  expected_return_at: string | null;
  returned_at: string | null;
  status: string;
  request_id: number | null;
  overdue_manual_sent_at: string | null;
  borrower_changes?: BorrowerChangeRecord[];
}

export interface BorrowerChangeRecord {
  id: number;
  record_id: number | null;
  request_id: number | null;
  borrower_before: string | null;
  borrower_before_user_id: string | null;
  borrower_before_open_id: string | null;
  borrower_before_avatar_url: string | null;
  borrower_before_job_title: string | null;
  borrower_after: string | null;
  borrower_after_user_id: string | null;
  borrower_after_open_id: string | null;
  borrower_after_avatar_url: string | null;
  borrower_after_job_title: string | null;
  expected_before: string | null;
  expected_after: string | null;
  changed_at: string;
}

export interface PortalUser {
  user_id?: string | null;
  open_id?: string | null;
  union_id?: string | null;
  name?: string | null;
  avatar_url?: string | null;
  job_title?: string | null;
  job_functions?: string[] | null;
  job_title_status?: string | null;
  profile_status?: string | null;
}

export interface PortalJwtSession {
  user: PortalUser;
  token: string;
  claims?: Record<string, unknown>;
  expiresAt?: number | string | null;
  audience?: string | null;
  audiences?: string[] | null;
  isTestUser?: boolean;
  isSoulknightProject?: boolean;
}

export interface PersonSnapshot {
  name?: string | null;
  avatar_url?: string | null;
  job_title?: string | null;
  job_functions?: string[] | null;
  job_title_status?: string | null;
  profile_status?: string | null;
}

export interface LLMModel {
  id: number;
  name: string;
  api_type: string;
  base_url: string;
  api_key: string;
  model: string;
  max_tokens: number;
  is_default: number;
}

export interface LLMModelAssignments {
  fast_model_id: number | null;
  accurate_model_id: number | null;
}

export interface NotificationParams {
  card_title: string;
  status: string;
  card_color: string;
  status_color: string;
}

export interface WebhookNotificationParams {
  card_title: string;
  body_template: string;
  card_color: string;
}

export interface NotificationSettingItem {
  key: string;
  label: string;
  description: string;
  defaults: NotificationParams;
  params: NotificationParams;
  customized: boolean;
}

export interface NotificationSettingsResponse {
  items: NotificationSettingItem[];
  color_options: string[];
}

export interface WebhookNotificationSettingItem {
  key: string;
  label: string;
  description: string;
  defaults: WebhookNotificationParams;
  params: WebhookNotificationParams;
  customized: boolean;
}

export interface WebhookNotificationSettingsResponse {
  items: WebhookNotificationSettingItem[];
  color_options: string[];
  admin_url: string;
}
