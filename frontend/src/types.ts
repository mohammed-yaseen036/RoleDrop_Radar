export type Profile = {
  id: string;
  email: string | null;
  skills: string[];
  target_role_families: string[];
  education_level: string | null;
  experience_indicators: string[];
  preferred_locations: string[];
  remote_preference: boolean;
  eligibility_notes: string[];
  confirmed: boolean;
  extraction_provider: string;
  extracted_at: string;
};

export type Source = {
  id: string;
  key: string;
  company: string;
  adapter: "ashby" | "greenhouse" | "lever" | "google";
  config: Record<string, string>;
  is_catalog: boolean;
};

export type Subscription = {
  id: string;
  enabled: boolean;
  notify_all_new_roles: boolean;
  initialized_at: string | null;
  source: Source;
};

export type Match = {
  score: number;
  verdict: string;
  eligible: boolean;
  matched_skills: string[];
  missing_requirements: string[];
  eligibility_warning: string | null;
  notification_reason: string;
  provider: string;
};

export type Job = {
  id: string;
  company: string;
  title: string;
  location: string | null;
  employment_type: string | null;
  description: string | null;
  canonical_url: string;
  apply_url: string;
  published_at: string | null;
  observed_at: string;
  match: Match | null;
};

export type Alert = {
  id: string;
  job_title: string;
  company: string;
  score: number;
  channel_type: "email" | "telegram";
  status: "sent" | "failed" | "skipped_configuration";
  error: string | null;
  created_at: string;
  sent_at: string | null;
};

export type UserSession = {
  email: string;
  userId?: string;
  token?: string;
};

