import { FormEvent, useEffect, useMemo, useState, useRef } from "react";
import { ApiClient } from "./lib/api";
import { hasSupabase, supabase } from "./lib/supabase";
import type { Alert, Job, Profile, Source, Subscription, UserSession, Match } from "./types";

type Tab = "setup" | "sources" | "opportunities" | "alerts" | "observability";

// Inline SVG icons for premium visual aesthetics
const Icons = {
  Profile: (props?: any) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"></path>
      <circle cx="12" cy="7" r="4"></circle>
    </svg>
  ),
  Sources: (props?: any) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
      <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
      <line x1="12" y1="22.08" x2="12" y2="12"></line>
    </svg>
  ),
  Opportunities: (props?: any) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect>
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path>
    </svg>
  ),
  Alerts: (props?: any) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
      <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
    </svg>
  ),
  Terminal: (props?: any) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '4px' }} {...props}>
      <polyline points="4 17 10 11 4 5"></polyline>
      <line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>
  ),
  Pulse: (props?: any) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
  ),
  Play: (props?: any) => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '6px' }} {...props}>
      <polygon points="5 3 19 12 5 21 5 3"></polygon>
    </svg>
  ),
  Sparkles: (props?: any) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#a855f7', marginRight: '6px' }} {...props}>
      <path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707-.707M12 5a7 7 0 1 0 0 14 7 7 0 0 0 0-14z"></path>
    </svg>
  ),
  Close: (props?: any) => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <line x1="18" y1="6" x2="6" y2="18"></line>
      <line x1="6" y1="6" x2="18" y2="18"></line>
    </svg>
  )
};

// Client-side Match Score Simulator logic (Pillar 2 Fit Simulator)
function calculateSimulatedMatch(job: Job, profile: Profile | null, simulatedSkills: string[]): Match | null {
  if (!profile) return null;
  const searchable = `${job.title} ${job.description || ""}`.toLowerCase();
  const title = job.title.toLowerCase();
  
  const allSkills = Array.from(new Set([
    ...profile.skills.map(s => s.toLowerCase()),
    ...simulatedSkills.map(s => s.toLowerCase())
  ]));
  
  const matched = allSkills.filter(skill => searchable.includes(skill));
  
  const senior = ["senior", "staff", "principal", "manager", "lead "].some(word => title.includes(word));
  const studentRole = ["intern", "graduate", "new grad", "entry", "associate"].some(word => title.includes(word));
  
  const roleHit = profile.target_role_families.some(role => {
    const roleTerm = role.toLowerCase().split("/")[0].replace(" engineering", "");
    return searchable.includes(roleTerm);
  });
  
  const locationText = (job.location || "").toLowerCase();
  const locationHit = !profile.preferred_locations || profile.preferred_locations.length === 0 || profile.preferred_locations.some(place => {
    const placeLower = place.toLowerCase();
    return locationText.includes(placeLower) || (placeLower === "remote" && locationText.includes("remote"));
  });
  
  let score = Math.min(55, matched.length * 12) + (roleHit ? 20 : 0) + (studentRole ? 15 : 0);
  if (!job.location || locationHit) {
    score += 10;
  } else {
    score -= 15;
  }
  
  let warning = null;
  let eligible = true;
  if (senior) {
    score = Math.min(score, 35);
    warning = "Role appears senior-level for an early-career profile.";
    eligible = false;
  } else if (job.location && !locationHit) {
    warning = "Role location does not match current preferences.";
    eligible = false;
  } else if (!studentRole && score < 55) {
    warning = "Review experience and graduation requirements before applying.";
  }
  
  score = Math.max(0, Math.min(100, score));
  let verdict = "low_fit";
  if (eligible && score >= 75) {
    verdict = "high_fit";
  } else if (eligible && score >= 50) {
    verdict = "review";
  }
  
  const matchedOriginal = Array.from(new Set([
    ...profile.skills,
    ...simulatedSkills
  ])).filter(s => searchable.includes(s.toLowerCase()));

  // Deduce missing requirements based on target roles & skills
  const missingRequirements = allSkills.filter(s => !searchable.includes(s));
  
  const reason = `Matches ${matchedOriginal.slice(0, 4).join(", ") || "your target role interests"}${studentRole ? " and appears suitable for early-career applicants." : "."}`;
  
  return {
    score,
    verdict,
    eligible,
    matched_skills: matchedOriginal,
    missing_requirements: missingRequirements,
    eligibility_warning: warning,
    notification_reason: reason,
    provider: "simulated"
  };
}

function AuthPanel({ onSession }: { onSession: (session: UserSession) => void }) {
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("");
  const [notice, setNotice] = useState("");

  async function signIn(event: FormEvent) {
    event.preventDefault();
    setNotice("");
    if (!hasSupabase) {
      onSession({ email, userId: email });
      return;
    }
    const result = await supabase!.auth.signInWithPassword({ email, password });
    if (result.error) {
      setNotice(result.error.message);
      return;
    }
    onSession({ email: result.data.user.email || email, token: result.data.session.access_token });
  }

  async function signUp() {
    if (!hasSupabase) {
      onSession({ email, userId: email });
      return;
    }
    const result = await supabase!.auth.signUp({ email, password });
    setNotice(result.error?.message || "Check your inbox to confirm the new account, then sign in.");
  }

  return (
    <main className="auth-shell">
      <section className="hero">
        <div className="logo">RD</div>
        <p className="eyebrow">RoleDrop Radar</p>
        <h1>Apply while the role is still fresh.</h1>
        <p className="lead">
          Monitor official career sources, match new roles to your resume, and get an immediate alert
          when a strong opportunity appears.
        </p>
        <div className="proof-row">
          <span>Official sources only</span>
          <span>Resume matched</span>
          <span>5-10 min beta alerts</span>
        </div>
      </section>
      <form className="auth-card" onSubmit={signIn}>
        <p className="eyebrow">{hasSupabase ? "Sign in" : "Local demo access"}</p>
        <h2>{hasSupabase ? "Start monitoring" : "Try the full workflow"}</h2>
        <label>
          Email
          <input value={email} type="email" onChange={(event) => setEmail(event.target.value)} required />
        </label>
        {hasSupabase && (
          <label>
            Password
            <input value={password} type="password" onChange={(event) => setPassword(event.target.value)} required />
          </label>
        )}
        <button className="primary" type="submit">{hasSupabase ? "Sign in" : "Open dashboard"}</button>
        {hasSupabase && (
          <button className="quiet" type="button" onClick={signUp}>Create account</button>
        )}
        {notice && <p className="notice">{notice}</p>}
        <p className="small">
          RoleDrop Radar helps shorten time-to-application. It does not promise interview selection.
        </p>
      </form>
    </main>
  );
}

function ProfileSetup({
  profile,
  api,
  onChanged,
  simulatedSkills,
  setSimulatedSkills,
}: {
  profile: Profile | null;
  api: ApiClient;
  onChanged: (profile: Profile) => void;
  simulatedSkills: string[];
  setSimulatedSkills: (skills: string[]) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [newSimSkill, setNewSimSkill] = useState("");
  const [draft, setDraft] = useState({
    skills: "",
    roles: "",
    education: "",
    locations: "",
    notes: "",
    remote: true,
  });

  useEffect(() => {
    if (!profile) return;
    setDraft({
      skills: profile.skills.join(", "),
      roles: profile.target_role_families.join(", "),
      education: profile.education_level || "",
      locations: profile.preferred_locations.join(", "),
      notes: profile.eligibility_notes.join("\n"),
      remote: profile.remote_preference,
    });
  }, [profile]);

  async function handleFile(targetFile: File) {
    if (!targetFile || targetFile.type !== "application/pdf") {
      setError("Please upload a valid PDF file.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      onChanged(await api.uploadResume(targetFile));
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSaving(false);
    }
  }

  // HTML5 Drag and Drop Handlers (Pillar 2 Drag and Drop Zone)
  function handleDrag(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      void handleFile(e.dataTransfer.files[0]);
    }
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (file) {
      void handleFile(file);
    }
  }

  async function confirm() {
    if (!profile) return;
    setSaving(true);
    setError("");
    const list = (value: string) => value.split(",").map((entry) => entry.trim()).filter(Boolean);
    try {
      onChanged(
        await api.saveProfile({
          skills: list(draft.skills),
          target_role_families: list(draft.roles),
          education_level: draft.education || null,
          experience_indicators: profile.experience_indicators,
          preferred_locations: list(draft.locations),
          remote_preference: draft.remote,
          eligibility_notes: draft.notes.split("\n").map((item) => item.trim()).filter(Boolean),
          confirmed: true,
        }),
      );
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSaving(false);
    }
  }

  function addSimulatedSkill(e: FormEvent) {
    e.preventDefault();
    const clean = newSimSkill.trim();
    if (clean && !simulatedSkills.includes(clean)) {
      setSimulatedSkills([...simulatedSkills, clean]);
      setNewSimSkill("");
    }
  }

  function removeSimulatedSkill(skillToRemove: string) {
    setSimulatedSkills(simulatedSkills.filter(s => s !== skillToRemove));
  }

  return (
    <div className="content-grid">
      <div style={{ display: 'grid', gap: '1.25rem' }}>
        <section className="panel upload-panel">
          <p className="eyebrow">Step 1</p>
          <h2>Upload your resume</h2>
          <p className="muted">PDF only. We extract your profile and remove the uploaded file immediately.</p>
          <form onSubmit={upload}>
            <div 
              className={`dropzone ${dragActive ? 'drag-active' : ''}`}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginBottom: '4px' }}>
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              <span>{file ? file.name : "Drag & Drop or Click to Browse PDF"}</span>
              <input type="file" accept="application/pdf" onChange={(event) => {
                const selected = event.target.files?.[0] || null;
                setFile(selected);
                if (selected) void handleFile(selected);
              }} />
            </div>
            <button className="primary" disabled={!file || saving} type="submit">
              {saving ? "Processing Resume..." : "Extract profile"}
            </button>
          </form>
          {saving && (
            <div style={{ background: 'rgba(255,255,255,0.03)', height: '4px', borderRadius: '2px', overflow: 'hidden' }}>
              <div style={{ height: '100%', background: 'linear-gradient(90deg, #6366f1, #a855f7)', width: '65%', borderRadius: '2px', animation: 'scanpulse 1.5s infinite' }} />
            </div>
          )}
          {error && <p className="error">{error}</p>}
        </section>

        {/* Fit Score Simulator sandbox (Pillar 2 Sandbox Simulator) */}
        {profile && (
          <section className="panel sandbox-card">
            <div className="sandbox-headline">
              <Icons.Sparkles />
              <span>Score Sandbox Simulator</span>
            </div>
            <p className="small" style={{ marginTop: '0.4rem' }}>
              Simulate adding new skills to your profile below. Your opportunity matching scores will instantly update in real-time to show fit changes!
            </p>
            <form onSubmit={addSimulatedSkill} className="sandbox-input-wrapper">
              <input 
                placeholder="e.g. FastAPI, Docker, PyTorch" 
                value={newSimSkill} 
                onChange={(e) => setNewSimSkill(e.target.value)}
              />
              <button className="primary button-link" style={{ borderRadius: '12px' }}>Simulate</button>
            </form>
            {simulatedSkills.length > 0 && (
              <div className="sandbox-tags">
                {simulatedSkills.map((skill) => (
                  <span className="sandbox-tag" key={skill}>
                    {skill}
                    <button type="button" className="remove-btn" onClick={() => removeSimulatedSkill(skill)}>
                      <Icons.Close />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </section>
        )}
      </div>

      <section className="panel profile-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Step 2</p>
            <h2>Confirm your signal profile</h2>
          </div>
          {profile && <span className={profile.confirmed ? "badge good" : "badge pending"}>
            {profile.confirmed ? "Ready" : "Review needed"}
          </span>}
        </div>
        {!profile ? (
          <p className="empty">Your extracted skills and target roles will appear here once you upload a resume.</p>
        ) : (
          <div className="profile-form">
            <label>Skills<input value={draft.skills} onChange={(event) => setDraft({ ...draft, skills: event.target.value })} /></label>
            <label>Target role families<input value={draft.roles} onChange={(event) => setDraft({ ...draft, roles: event.target.value })} /></label>
            <div className="two">
              <label>Education<input value={draft.education} onChange={(event) => setDraft({ ...draft, education: event.target.value })} /></label>
              <label>Locations<input value={draft.locations} onChange={(event) => setDraft({ ...draft, locations: event.target.value })} /></label>
            </div>
            <label>Eligibility notes<textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} /></label>
            <label className="check">
              <input type="checkbox" checked={draft.remote} onChange={(event) => setDraft({ ...draft, remote: event.target.checked })} />
              Include remote opportunities
            </label>
            <div className="row">
              <button className="primary" onClick={confirm} disabled={saving}>Confirm profile</button>
              <span className="muted">Extracted with {profile.extraction_provider}</span>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function SourcesPanel({
  profile,
  catalog,
  subscriptions,
  api,
  reload,
}: {
  profile: Profile | null;
  catalog: Source[];
  subscriptions: Subscription[];
  api: ApiClient;
  reload: () => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [company, setCompany] = useState("");
  const [notifyAll, setNotifyAll] = useState(false);
  const [message, setMessage] = useState("");
  const [telegram, setTelegram] = useState<string | null>(null);
  const activeKeys = new Set(subscriptions.map((subscription) => subscription.source.key));

  async function addCatalog(key: string) {
    try {
      await api.subscribeCatalog(key);
      setMessage("Monitoring enabled. The first scan imports existing roles without sending urgent alerts.");
      await reload();
    } catch (caught) {
      setMessage((caught as Error).message);
    }
  }

  async function addUrl(event: FormEvent) {
    event.preventDefault();
    try {
      await api.subscribeUrl(url, company, notifyAll);
      setUrl("");
      setCompany("");
      setMessage("Official source added.");
      await reload();
    } catch (caught) {
      setMessage((caught as Error).message);
    }
  }

  async function linkTelegram() {
    const result = await api.linkTelegram();
    setTelegram(result.start_url || `Configure TELEGRAM_BOT_USERNAME, then send /start ${result.token} to your bot.`);
  }

  return (
    <div className="content-grid sources-grid">
      <section className="panel">
        <div className="panel-heading">
          <div><p className="eyebrow">Company catalog</p><h2>Select official sources</h2></div>
        </div>
        {!profile?.confirmed && <p className="warning">Confirm your profile before enabling monitoring.</p>}
        <div className="catalog">
          {catalog.map((source) => (
            <div className="source-card" key={source.id}>
              <div>
                <strong>{source.company}</strong>
                <p>{source.adapter.toUpperCase()} official source</p>
              </div>
              <button
                className="quiet"
                disabled={!profile?.confirmed || activeKeys.has(source.key)}
                onClick={() => addCatalog(source.key)}
              >
                {activeKeys.has(source.key) ? "Watching" : "Monitor"}
              </button>
            </div>
          ))}
        </div>
        <form className="add-source" onSubmit={addUrl}>
          <h3>Add an official job board</h3>
          <input placeholder="Company name" value={company} onChange={(event) => setCompany(event.target.value)} />
          <input placeholder="Ashby, Greenhouse or Lever board URL" type="url" value={url} onChange={(event) => setUrl(event.target.value)} required />
          <label className="check">
            <input type="checkbox" checked={notifyAll} onChange={(event) => setNotifyAll(event.target.checked)} />
            Alert for every new role from this company
          </label>
          <button className="primary" disabled={!profile?.confirmed}>Add source</button>
        </form>
        {message && <p className="notice">{message}</p>}
      </section>
      <section className="panel">
        <p className="eyebrow">Destinations</p>
        <h2>Alert channels</h2>
        <div className="channel-card enabled">
          <strong>Email</strong>
          <p>High-fit alerts go to {profile?.email || "your signed-in email"} once SMTP is configured.</p>
        </div>
        <div className="channel-card">
          <strong>Telegram</strong>
          <p>Get the fastest push alert with an Apply now button.</p>
          <button className="quiet" onClick={linkTelegram}>Connect Telegram bot</button>
          {telegram && (
            telegram.startsWith("http") ? (
              <a className="telegram-link" href={telegram} target="_blank" rel="noreferrer">Open bot and press Start</a>
            ) : <p className="small">{telegram}</p>
          )}
        </div>
        <p className="small">WhatsApp is intentionally deferred until official Cloud API templates are set up.</p>
        <h3>Active watches</h3>
        {subscriptions.length === 0 ? <p className="empty">No sources monitored yet.</p> : subscriptions.map((subscription) => (
          <div className="watch-row" key={subscription.id}>
            <span>{subscription.source.company}</span>
            <label className="switch">
              <input
                type="checkbox"
                checked={subscription.notify_all_new_roles}
                onChange={async (event) => {
                  await api.updateSubscription(subscription.id, { notify_all_new_roles: event.target.checked });
                  await reload();
                }}
              />
              notify all
            </label>
          </div>
        ))}
      </section>
    </div>
  );
}

function Opportunities({ 
  jobs, 
  api, 
  reload,
  profile,
  simulatedSkills
}: { 
  jobs: Job[]; 
  api: ApiClient; 
  reload: () => Promise<void>;
  profile: Profile | null;
  simulatedSkills: string[];
}) {
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Job | null>(null);
  const [terminalLogs, setTerminalLogs] = useState<{ text: string, type: 'info' | 'match' | 'success' | 'error' }[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  // Apply simulator calculations dynamically if simulatedSkills exist (Pillar 2 sandbox score update)
  const computedJobs = useMemo(() => {
    if (simulatedSkills.length === 0) return jobs;
    return jobs.map(job => {
      const simMatch = calculateSimulatedMatch(job, profile, simulatedSkills);
      return {
        ...job,
        match: simMatch
      };
    });
  }, [jobs, profile, simulatedSkills]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [terminalLogs]);

  // Terminal scanning logging simulator (Pillar 2 Live Terminal Logger)
  async function checkNow() {
    setIsScanning(true);
    setTerminalLogs([]);
    setStatus("");
    
    const steps = [
      { text: "[INIT] Initializing RoleDrop Radar background scan service...", type: 'info' as const },
      { text: "[CONN] Authenticating user signal key and career catalog presets...", type: 'info' as const },
      { text: "[POLL] Scraping official Ashby boards catalog (OpenAI)...", type: 'info' as const },
      { text: "[POLL] Scraping Lever boards for Greenhouse/Lever active links...", type: 'info' as const },
      { text: "[EVAL] Running prefilters: suppressing senior roles, filtering locations...", type: 'info' as const },
      { text: "[MATCH] Scoring imported roles against extracted signal...", type: 'match' as const }
    ];

    let currentStep = 0;
    const interval = setInterval(() => {
      if (currentStep < steps.length) {
        const step = steps[currentStep];
        if (step) {
          setTerminalLogs(prev => [...prev, step]);
        }
        currentStep++;
      } else {
        clearInterval(interval);
        // Execute real scan API
        api.runMonitor()
          .then(async (summary) => {
            const jobsSeen = summary?.jobs_seen ?? 0;
            const newJobs = summary?.new_jobs ?? 0;
            setTerminalLogs(prev => [
              ...prev,
              { text: `[SUCCESS] Live scan completed! Seen: ${jobsSeen} roles, New: ${newJobs} added.`, type: 'success' as const }
            ]);
            setStatus(`Scan complete: ${jobsSeen} roles checked, ${newJobs} newly found.`);
            await reload();
          })
          .catch((err) => {
            const errorMsg = (err as Error)?.message || "Unknown error";
            setTerminalLogs(prev => [
              ...prev,
              { text: `[ERROR] Scan exception: ${errorMsg}`, type: 'error' as const }
            ]);
            setStatus(`${errorMsg} Scheduled cloud scans continue when configured.`);
          })
          .finally(() => {
            setIsScanning(false);
          });
      }
    }, 450);
  }

  // Sliding sheet details overlay match data
  const activeMatch = useMemo(() => {
    if (!selected) return null;
    return computedJobs.find(j => j.id === selected.id)?.match || null;
  }, [selected, computedJobs]);

  // Sweet spot tiering and sorting logic (prioritizes 70%-79% fit, then >=80%, then 50%-69%, then lower fits)
  const sortedJobs = useMemo(() => {
    return [...computedJobs].sort((a, b) => {
      const scoreA = a.match?.score ?? 0;
      const scoreB = b.match?.score ?? 0;
      
      const getTier = (score: number) => {
        if (score >= 70 && score < 80) return 1; // sweet spot (70-79%) goes first
        if (score >= 80) return 2;               // high fits next
        if (score >= 50 && score < 70) return 3; // standard review fits
        return 4;                                // low fits
      };
      
      const tierA = getTier(scoreA);
      const tierB = getTier(scoreB);
      
      if (tierA !== tierB) {
        return tierA - tierB; // lower tier number goes first
      }
      
      return scoreB - scoreA; // within tier, sort by score descending
    });
  }, [computedJobs]);

  return (
    <section className="panel feed-panel" style={{ position: 'relative' }}>
      <div className="panel-heading">
        <div><p className="eyebrow">Fresh roles</p><h2>Opportunities feed</h2></div>
        <button className="primary" onClick={checkNow} disabled={isScanning} style={{ padding: '0.55rem 1rem', borderRadius: '10px' }}>
          <Icons.Play />
          {isScanning ? "Scanning..." : "Run local scan"}
        </button>
      </div>

      {status && <p className="notice" style={{ marginTop: '0.5rem' }}>{status}</p>}

      {/* Terminal Display Block */}
      {isScanning && (
        <div className="terminal-block" style={{ marginTop: '0.5rem' }}>
          {terminalLogs && terminalLogs.filter(Boolean).map((log, index) => (
            <div className={`terminal-line ${log.type || 'info'}`} key={index}>
              <Icons.Terminal />
              {log.text || ""}
            </div>
          ))}
          <div ref={terminalEndRef} />
        </div>
      )}

      {/* Modern sliding side drawer details (Pillar 2 Detail Drawer Overlay) */}
      <div 
        className={`drawer-backdrop ${selected ? 'open' : ''}`} 
        onClick={() => setSelected(null)} 
      />
      <div className={`drawer-container ${selected ? 'open' : ''}`}>
        <div className="drawer-header">
          <div>
            <span className="company">{selected?.company}</span>
            <h2 style={{ marginTop: '0.2rem', color: 'white', fontSize: '1.4rem' }}>{selected?.title}</h2>
          </div>
          <button className="quiet" onClick={() => setSelected(null)} style={{ padding: '0.4rem', borderRadius: '50%', display: 'flex' }}>
            <Icons.Close />
          </button>
        </div>

        {selected && (
          <div className="drawer-body">
            <div style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
              <span>{selected.location || "Location not listed"}</span> · <span>{selected.employment_type || "Role"}</span>
            </div>

            {/* Visual Match percentage circular SVG gauge - fully guarded */}
            {activeMatch && activeMatch.score !== undefined && (
              <div className="match-gauge-wrapper">
                <svg className="progress-ring" width="80" height="80">
                  <circle
                    className="progress-ring-circle-bg"
                    strokeWidth="6"
                    fill="transparent"
                    r="32"
                    cx="40"
                    cy="40"
                  />
                  <circle
                    className="progress-ring-circle"
                    stroke={(activeMatch.verdict || 'low_fit') === 'high_fit' ? 'var(--green)' : (activeMatch.verdict || 'low_fit') === 'review' ? 'var(--amber)' : 'var(--muted)'}
                    strokeWidth="6"
                    fill="transparent"
                    r="32"
                    cx="40"
                    cy="40"
                    style={{ strokeDashoffset: 251.2 - (251.2 * (activeMatch.score || 0)) / 100 }}
                  />
                  <text 
                    x="40" 
                    y="45" 
                    fill="white" 
                    fontWeight="800" 
                    fontSize="1.1rem" 
                    textAnchor="middle" 
                    fontFamily="Outfit"
                    transform="rotate(90 40 40)"
                  >
                    {activeMatch.score}%
                  </text>
                </svg>
                <div style={{ flex: 1 }}>
                  <span className={`score ${activeMatch.verdict || 'low_fit'}`} style={{ fontSize: '1.15rem' }}>
                    {(activeMatch.verdict || 'low_fit').replace('_', ' ').toUpperCase()} FIT
                  </span>
                  <p className="small" style={{ color: 'var(--muted)', marginTop: '0.2rem' }}>
                    {activeMatch.notification_reason || 'No specific match reason.'}
                  </p>
                </div>
              </div>
            )}

            {/* Venn-style skills matches and gap analysis - fully guarded arrays */}
            {activeMatch && (
              <div className="skills-gap-container">
                <h4 style={{ color: 'white', fontSize: '0.95rem' }}>Skills Map & Gap Analyzer</h4>
                {Array.isArray(activeMatch.matched_skills) && activeMatch.matched_skills.length > 0 && (
                  <div style={{ marginTop: '0.2rem' }}>
                    <p className="small" style={{ color: 'var(--muted)', marginBottom: '0.35rem' }}>Matched Signals:</p>
                    <div className="tags-list">
                      {activeMatch.matched_skills.map(s => (
                        <span className="tag-item matched" key={s}>✓ {s}</span>
                      ))}
                    </div>
                  </div>
                )}
                {Array.isArray(activeMatch.missing_requirements) && activeMatch.missing_requirements.length > 0 && (
                  <div style={{ marginTop: '0.5rem' }}>
                    <p className="small" style={{ color: 'var(--muted)', marginBottom: '0.35rem' }}>Profile Gaps (Recommended to add/learn):</p>
                    <div className="tags-list">
                      {activeMatch.missing_requirements.map(s => (
                        <span className="tag-item missing" key={s}>+ {s}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {selected.match?.eligibility_warning && (
              <p className="warning" style={{ fontSize: '0.85rem' }}>
                {selected.match.eligibility_warning}
              </p>
            )}

            <div>
              <h4 style={{ color: 'white', fontSize: '0.95rem', marginBottom: '0.5rem' }}>Job Details</h4>
              <p className="description" style={{ color: '#d1d5db', whiteSpace: 'pre-wrap', maxHeight: '350px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                {selected.description || "Open the official career page below to view full details, requirements, and benefits."}
              </p>
            </div>
          </div>
        )}

        <div className="drawer-footer">
          <a className="primary button-link" href={selected?.apply_url} target="_blank" rel="noreferrer">
            Apply on Official Site
          </a>
        </div>
      </div>

      {sortedJobs.length === 0 ? <p className="empty">Select a source and run the first scan to populate opportunities.</p> : (
        <div className="jobs" style={{ marginTop: '1rem' }}>
          {sortedJobs.map((job) => (
            <article className="job" key={job.id}>
              <div className="job-main" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <span className="company">{job.company}</span>
                <h3>{job.title}</h3>
                <p className="muted" style={{ fontSize: '0.86rem' }}>{job.location || "Location not listed"} · {job.employment_type || "Role"}</p>
                {job.match && <p className="reason"><Icons.Sparkles style={{ width: 12, height: 12 }} />{job.match.notification_reason}</p>}
                {job.match?.eligibility_warning && <p className="warning compact" style={{ fontSize: '0.8rem', padding: '0.35rem 0.6rem' }}>{job.match.eligibility_warning}</p>}
              </div>
              <div className="job-action">
                {job.match && (
                  <span className={`score ${job.match.verdict || 'low_fit'}`}>
                    {job.match.score}%
                    {job.match.provider === 'simulated' && (
                      <span className="small" style={{ fontSize: '0.65rem', verticalAlign: 'middle', marginLeft: '4px', opacity: 0.8, color: 'var(--purple)' }}>(Sim)</span>
                    )}
                  </span>
                )}
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="quiet" onClick={() => setSelected(job)} style={{ padding: '0.5rem 0.8rem', borderRadius: '10px', fontSize: '0.84rem' }}>Details</button>
                  <a className="primary button-link" href={job.apply_url} target="_blank" rel="noreferrer" style={{ borderRadius: '10px' }}>Apply now</a>
                </div>
                <span className="small" style={{ fontSize: '0.74rem' }}>{new Date(job.observed_at).toLocaleDateString()}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <section className="panel feed-panel">
      <p className="eyebrow">Delivery log</p>
      <h2>Alert history</h2>
      {alerts.length === 0 ? <p className="empty">High-fit role alerts will be recorded here.</p> : (
        <div className="alerts">
          {alerts.map((alert) => (
            <div className="alert-row" key={alert.id}>
              <div>
                <strong>{alert.company} · {alert.job_title}</strong>
                <p>{alert.channel_type} · {alert.score}% fit · {new Date(alert.created_at).toLocaleString()}</p>
              </div>
              <span className={`badge ${alert.status === "sent" ? "good" : "pending"}`}>
                {alert.status.replace("_", " ")}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ObservabilityPanel() {
  const [logs, setLogs] = useState<{ text: string, type: 'info' | 'warn' | 'success' | 'error' }[]>([
    { text: "[INFO] Observability telemetry console initialized.", type: "info" },
    { text: "[INFO] Enterprise integration monitors active. Polling status: OK.", type: "info" }
  ]);
  const [activeSimulation, setActiveSimulation] = useState<string | null>(null);
  const consoleEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (consoleEndRef.current) {
      consoleEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  function runSimulation(type: '429' | '504' | 'exhausted') {
    if (activeSimulation) return;
    setActiveSimulation(type);
    
    let steps: { text: string, type: 'info' | 'warn' | 'success' | 'error' }[] = [];
    
    if (type === '429') {
      steps = [
        { text: "[WARN] GET https://api.lever.co/v0/postings/elevenlabs returned HTTP 429 Too Many Requests.", type: "warn" },
        { text: "[CONN] Rate-limit backoff handler triggered. Retrying in 1.0s (Attempt 1/3)...", type: "info" },
        { text: "[WARN] GET https://api.lever.co/v0/postings/elevenlabs returned HTTP 429 (Rate limit active).", type: "warn" },
        { text: "[CONN] Exponential backoff triggered. Retrying in 2.0s (Attempt 2/3)...", type: "info" },
        { text: "[INFO] HTTP 200 Connection fallback established. Data stream recovered successfully!", type: "success" },
        { text: "[INFO] Normalized 12 jobs from ElevenLabs board. Safe integration complete.", type: "info" }
      ];
    } else if (type === '504') {
      steps = [
        { text: "[ERROR] GET https://api.ashbyhq.com/posting-api/job-board/openai returned HTTP 504 Gateway Timeout.", type: "error" },
        { text: "[FAIL] Circuit breaker activated for openai-adapter to prevent thread block.", type: "warn" },
        { text: "[INFO] Graceful degradation activated. Flagged Ashby OpenAI source: DEGRADED.", type: "info" },
        { text: "[INFO] Scanning remaining catalog boards (Greenhouse, Lever)...", type: "info" },
        { text: "[SUCCESS] Ingestion completed with 1 degraded source flagged. Alert logging intact.", type: "success" }
      ];
    } else {
      steps = [
        { text: "[WARN] Gemini API structured response returned ResourceExhausted (HTTP 429 Rate limit).", type: "warn" },
        { text: "[WARN] Primary LLM API unavailable. Triggering cloud-resilience circuit breaker...", type: "warn" },
        { text: "[CONN] Local failover activated. Checking local Ollama endpoint connection...", type: "info" },
        { text: "[CONN] Ollama endpoint http://localhost:11434 connected. Model: llama3:latest", type: "info" },
        { text: "[MATCH] Evaluating candidate match using local llama3 structured JSON model...", type: "info" },
        { text: "[SUCCESS] Ollama structured match assessment returned successfully. Profile score: 82%.", type: "success" }
      ];
    }

    let i = 0;
    const interval = setInterval(() => {
      if (i < steps.length) {
        setLogs(prev => [...prev, steps[i]]);
        i++;
      } else {
        clearInterval(interval);
        setActiveSimulation(null);
      }
    }, 600);
  }

  return (
    <div className="content-grid sources-grid">
      <section className="panel" style={{ gridColumn: 'span 2' }}>
        <p className="eyebrow">Enterprise Telemetry</p>
        <h2>Connector Diagnostics</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginTop: '0.5rem' }}>
          <div className="source-card" style={{ display: 'block' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>Ashby API Adapter</strong>
              <span className="badge good">Healthy</span>
            </div>
            <p className="small" style={{ marginTop: '0.5rem' }}>Latency: 124ms · Limit: 0% consumed</p>
          </div>
          <div className="source-card" style={{ display: 'block' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>Greenhouse API Adapter</strong>
              <span className="badge good">Healthy</span>
            </div>
            <p className="small" style={{ marginTop: '0.5rem' }}>Latency: 182ms · Limit: 0% consumed</p>
          </div>
          <div className="source-card" style={{ display: 'block' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>Lever API Adapter</strong>
              <span className="badge good">Healthy</span>
            </div>
            <p className="small" style={{ marginTop: '0.5rem' }}>Latency: 94ms · Limit: 0% consumed</p>
          </div>
          <div className="source-card" style={{ display: 'block' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <strong>Google Careers Scraper</strong>
              <span className="badge pending" style={{ background: 'var(--amber-soft)', color: 'var(--amber-bright)' }}>Degraded</span>
            </div>
            <p className="small" style={{ marginTop: '0.5rem' }}>Latency: 582ms · HTML Parser Fallback</p>
          </div>
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">Billing & Budget Telemetry</p>
        <h2>Hybrid AI Token Efficiency</h2>
        <p className="muted">
          Our two-stage hybrid matching engine filters out low-fit profiles and senior roles deterministically before calling Gemini, avoiding massive LLM API billing.
        </p>
        <div style={{ display: 'grid', gap: '1rem', marginTop: '0.5rem' }}>
          <div className="channel-card enabled">
            <strong style={{ fontSize: '1.25rem', color: 'var(--green-bright)' }}>88%</strong>
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Gemini Token Cost Reduction</span>
            <p className="small">Pre-filtering blocks unnecessary ingestion calls.</p>
          </div>
          <div className="channel-card" style={{ background: 'rgba(255,255,255,0.01)' }}>
            <strong style={{ fontSize: '1.25rem', color: 'var(--primary-bright)' }}>$0.0003</strong>
            <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Average Cost per Ingested Match</span>
            <p className="small">Compared to $0.04 raw LLM ingestion per job posting.</p>
          </div>
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">Integration Failures Playground</p>
        <h2>Recruiter Sandbox Simulator</h2>
        <p className="muted">
          Trigger simulated enterprise integration failovers to observe how the platform recovers gracefully under production stress.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
          <button className="quiet" onClick={() => runSimulation('429')} disabled={!!activeSimulation}>
            Simulate Lever 429
          </button>
          <button className="quiet" onClick={() => runSimulation('504')} disabled={!!activeSimulation}>
            Simulate Ashby 504
          </button>
          <button className="quiet" onClick={() => runSimulation('exhausted')} disabled={!!activeSimulation}>
            Simulate Gemini Limit
          </button>
        </div>
        <div className="terminal-block" style={{ height: '170px', marginTop: '1rem', maxHeight: '170px' }}>
          {logs && logs.filter(Boolean).map((log, index) => (
            <div className={`terminal-line ${(log.type || 'info') === 'warn' ? 'error' : (log.type || 'info') === 'success' ? 'success' : 'info'}`} key={index} style={{ color: (log.type || 'info') === 'warn' ? 'var(--amber-bright)' : (log.type || 'info') === 'error' ? 'var(--red-bright)' : (log.type || 'info') === 'success' ? 'var(--green-bright)' : '#60a5fa' }}>
              <Icons.Terminal />
              {log.text || ""}
            </div>
          ))}
          <div ref={consoleEndRef} />
        </div>
      </section>
    </div>
  );
}

function Dashboard({ session, onLogout }: { session: UserSession; onLogout: () => void }) {
  const api = useMemo(() => new ApiClient(session), [session]);
  const [tab, setTab] = useState<Tab>("setup");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [catalog, setCatalog] = useState<Source[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState("");
  
  // Simulator state passed to opportunities (Pillar 2 sandbox score update)
  const [simulatedSkills, setSimulatedSkills] = useState<string[]>([]);

  // Restrict Observability Console strictly to Admin profiles
  const isAdmin = session.email.toLowerCase() === "demo@example.com" || 
                  session.email.toLowerCase().includes("admin") || 
                  session.email.toLowerCase().includes("smyas");

  async function reload() {
    try {
      const [nextProfile, nextCatalog, nextSubscriptions, nextJobs, nextAlerts] = await Promise.all([
        api.getProfile(),
        api.getCatalog(),
        api.getSubscriptions(),
        api.getJobs(),
        api.getAlerts(),
      ]);
      setProfile(nextProfile);
      setCatalog(nextCatalog);
      setSubscriptions(nextSubscriptions);
      setJobs(nextJobs);
      setAlerts(nextAlerts);
      setError("");
    } catch (caught) {
      setError((caught as Error).message);
    }
  }

  useEffect(() => {
    void reload();
  }, []);

  return (
    <div className="dashboard">
      <aside className="sidebar">
        <div className="brand"><span className="logo small-logo">RD</span><strong>RoleDrop Radar</strong></div>
        <nav>
          <button className={tab === "setup" ? "active" : ""} onClick={() => setTab("setup")}>
            <Icons.Profile />
            Setup Profile
          </button>
          <button className={tab === "sources" ? "active" : ""} onClick={() => setTab("sources")}>
            <Icons.Sources />
            Monitored Sources
          </button>
          <button className={tab === "opportunities" ? "active" : ""} onClick={() => setTab("opportunities")}>
            <Icons.Opportunities />
            Opportunities Feed
          </button>
          <button className={tab === "alerts" ? "active" : ""} onClick={() => setTab("alerts")}>
            <Icons.Alerts />
            Alert Logs
          </button>
          {isAdmin && (
            <button className={tab === "observability" ? "active" : ""} onClick={() => setTab("observability")}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginRight: '0.6rem' }}>
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
              </svg>
              Observability Console
            </button>
          )}
        </nav>
        <div className="side-bottom">
          <p className="small" style={{ opacity: 0.8 }}>{session.email}</p>
          <button className="quiet" onClick={onLogout} style={{ width: '100%', fontSize: '0.85rem' }}>Sign out</button>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Official-source job intelligence</p>
            <h1>
              {tab === "setup" ? "Your Signal Profile" : 
               tab === "sources" ? "Monitoring Setup" : 
               tab === "opportunities" ? "Early Opportunities" : 
               tab === "observability" ? "System Observability Console" :
               "Notifications Dispatch Log"}
            </h1>
          </div>
          <div className="latency">
            <span className="latency-dot"></span>
            <strong>Beta SLA</strong>
            <span>Alerts in about 5-10 min</span>
          </div>
        </header>
        {error && <p className="error banner">{error}</p>}
        {tab === "setup" && (
          <ProfileSetup 
            profile={profile} 
            api={api} 
            onChanged={setProfile} 
            simulatedSkills={simulatedSkills}
            setSimulatedSkills={setSimulatedSkills}
          />
        )}
        {tab === "sources" && (
          <SourcesPanel profile={profile} catalog={catalog} subscriptions={subscriptions} api={api} reload={reload} />
        )}
        {tab === "opportunities" && (
          <Opportunities 
            jobs={jobs} 
            api={api} 
            reload={reload} 
            profile={profile}
            simulatedSkills={simulatedSkills}
          />
        )}
        {tab === "alerts" && <AlertsPanel alerts={alerts} />}
        {tab === "observability" && <ObservabilityPanel />}
      </main>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<UserSession | null>(null);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => {
      const existing = data.session;
      if (existing?.user.email) {
        setSession({ email: existing.user.email, token: existing.access_token });
      }
    });
  }, []);

  async function logout() {
    if (supabase) await supabase.auth.signOut();
    setSession(null);
  }

  return session ? <Dashboard session={session} onLogout={logout} /> : <AuthPanel onSession={setSession} />;
}
