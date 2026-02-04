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
  borrowed_at: string | null;
  expected_return_at: string | null;
}

export interface BorrowRequestItem {
  id: number;
  device_id: number;
  device_model: string;
  borrower_name: string;
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
  borrowed_at: string;
  expected_return_at: string | null;
  returned_at: string | null;
  status: string;
  request_id: number | null;
  borrower_changes?: BorrowerChangeRecord[];
}

export interface BorrowerChangeRecord {
  id: number;
  record_id: number | null;
  request_id: number | null;
  borrower_before: string | null;
  borrower_after: string | null;
  expected_before: string | null;
  expected_after: string | null;
  changed_at: string;
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
