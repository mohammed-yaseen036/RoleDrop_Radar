import type { Alert, Job, Profile, Source, Subscription, UserSession } from "../types";

const baseUrl = (import.meta.env.VITE_API_URL as string | undefined) || "http://localhost:8000";

export class ApiClient {
  constructor(private session: UserSession) {}

  private headers(extra?: HeadersInit): Headers {
    const headers = new Headers(extra);
    if (this.session.token) {
      headers.set("Authorization", `Bearer ${this.session.token}`);
    } else {
      headers.set("X-Demo-User", this.session.userId || this.session.email);
      headers.set("X-Demo-Email", this.session.email);
    }
    return headers;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: this.headers(init?.headers),
    });
    if (!response.ok) {
      const result = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(result.detail || "Request failed");
    }
    return response.json() as Promise<T>;
  }

  getProfile() {
    return this.request<Profile | null>("/api/profile");
  }

  uploadResume(file: File) {
    const data = new FormData();
    data.append("resume", file);
    return this.request<Profile>("/api/profile/resume", { method: "POST", body: data });
  }

  saveProfile(profile: Omit<Profile, "id" | "email" | "extraction_provider" | "extracted_at">) {
    return this.request<Profile>("/api/profile", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
  }

  getCatalog() {
    return this.request<Source[]>("/api/sources/catalog");
  }

  getSubscriptions() {
    return this.request<Subscription[]>("/api/subscriptions");
  }

  subscribeCatalog(catalogKey: string) {
    return this.request<Subscription>("/api/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ catalog_key: catalogKey }),
    });
  }

  subscribeUrl(url: string, companyName: string, notifyAll: boolean) {
    return this.request<Subscription>("/api/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        official_board_url: url,
        company_name: companyName || undefined,
        notify_all_new_roles: notifyAll,
      }),
    });
  }

  updateSubscription(id: string, payload: Partial<Pick<Subscription, "enabled" | "notify_all_new_roles">>) {
    return this.request<Subscription>(`/api/subscriptions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  getJobs() {
    return this.request<Job[]>("/api/jobs");
  }

  getAlerts() {
    return this.request<Alert[]>("/api/alerts");
  }

  linkTelegram() {
    return this.request<{ start_url: string | null; token: string; instructions: string }>("/api/integrations/telegram/link", {
      method: "POST",
    });
  }

  runMonitor() {
    return this.request<{ jobs_seen: number; new_jobs: number; alerts_attempted: number }>("/api/monitor/run", {
      method: "POST",
    });
  }
}

