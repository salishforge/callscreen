/** Shared API types matching the backend Pydantic schemas. */

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "caretaker" | "user";
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export type ContactType = "whitelist" | "blocklist" | "known";
export type ContactCategory =
  | "personal"
  | "medical"
  | "business"
  | "government"
  | "other";

export interface Contact {
  id: string;
  phone_number: string;
  name: string;
  contact_type: ContactType;
  category: ContactCategory;
  trust_override: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface ContactCreate {
  phone_number: string;
  name: string;
  contact_type: ContactType;
  category: ContactCategory;
  trust_override?: number | null;
  notes?: string;
}

export type CallStatus =
  | "incoming"
  | "triage"
  | "number_lookup"
  | "screening"
  | "interviewing"
  | "deciding"
  | "forwarding"
  | "messaging"
  | "blocking"
  | "engaging"
  | "completed"
  | "failed";

export type CallDisposition =
  | "forwarded"
  | "messaged"
  | "blocked"
  | "engaged"
  | "emergency"
  | "abandoned";

export interface CallRecord {
  id: string;
  call_sid: string;
  from_number: string;
  to_number: string;
  status: CallStatus;
  disposition: CallDisposition | null;
  trust_score: number | null;
  stir_attestation: string;
  caller_name: string | null;
  caller_intent: string | null;
  ai_summary: string | null;
  started_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  created_at: string;
}

export type MessagePriority = "urgent" | "normal" | "low";
export type MessageCategory = "medical" | "personal" | "business" | "other";

export interface Message {
  id: string;
  call_id: string;
  content: string;
  summary: string | null;
  priority: MessagePriority;
  category: MessageCategory;
  audio_ref: string | null;
  delivery_status: "pending" | "delivered" | "failed";
  delivered_via: string | null;
  read_at: string | null;
  created_at: string;
}

export interface UserSettings {
  preferred_channel: string;
  greeting_message: string;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  quiet_hours_timezone: string;
  caretaker_fork_enabled: boolean;
  caretaker_fork_priority: string;
  screening_strictness: string;
}

export interface NumberIntel {
  phone_number: string;
  carrier_name: string | null;
  line_type: string;
  cnam: string | null;
  composite_trust_score: number | null;
  is_medical_provider: boolean;
  ftc_complaint_count: number | null;
  community_blocklist_hit: boolean;
  call_count: number;
  last_seen: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}
