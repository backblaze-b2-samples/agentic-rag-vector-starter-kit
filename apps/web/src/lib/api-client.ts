import type {
  AgentBehavior,
  ChatRequest,
  ChatResponse,
  ChatSession,
  DailyUploadCount,
  DashboardStats,
  FileMetadata,
  FileUploadResponse,
  IngestionLogEntry,
  QueryLogEntry,
  RetrievalQuality,
  SessionMessageDetail,
  SessionSummary,
  UploadStats,
} from "@vibe-coding-starter-kit/shared";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Typed API error with HTTP status code for caller-side branching. */
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True for 408, 429, 500, 502, 503, 504 — worth retrying. */
  get isRetryable(): boolean {
    return [408, 429, 500, 502, 503, 504].includes(this.status);
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  get isConflict(): boolean {
    return this.status === 409;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    // Network failure (offline, DNS, CORS, etc.)
    throw new ApiError("Network error — check your connection", 0);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      body.detail || `API error: ${res.status}`,
      res.status,
    );
  }
  return res.json();
}

export async function getHealth() {
  return apiFetch<{ status: string; b2_connected: boolean }>("/health");
}

export async function getFiles(prefix = "", limit = 100) {
  return apiFetch<FileMetadata[]>(
    `/files?prefix=${encodeURIComponent(prefix)}&limit=${limit}`
  );
}

export async function getFileStats() {
  return apiFetch<UploadStats>("/files/stats");
}

export async function getUploadActivity(days = 7) {
  return apiFetch<DailyUploadCount[]>(`/files/stats/activity?days=${days}`);
}

export async function getFile(key: string) {
  return apiFetch<FileMetadata>(`/files/${key}`);
}

export async function getDownloadUrl(key: string) {
  return apiFetch<{ url: string }>(`/files/${key}/download`);
}

export async function deleteFile(key: string) {
  return apiFetch<{ deleted: boolean; key: string }>(`/files/${key}`, {
    method: "DELETE",
  });
}

// --- Chat Session API ---

export async function listChatSessions(limit = 50) {
  return apiFetch<ChatSession[]>(`/chat/sessions?limit=${limit}`);
}

export async function createChatSession() {
  return apiFetch<ChatSession>("/chat/sessions", { method: "POST" });
}

export async function getChatSession(sessionId: string) {
  return apiFetch<{ session: ChatSession; messages: unknown[] }>(
    `/chat/sessions/${sessionId}`,
  );
}

export async function deleteChatSession(sessionId: string) {
  return apiFetch<{ deleted: boolean }>(`/chat/sessions/${sessionId}`, {
    method: "DELETE",
  });
}

// --- Chat API ---

export async function sendChatMessage(request: ChatRequest) {
  return apiFetch<ChatResponse>("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

/** SSE streaming chat — returns an EventSource-like async iterator. */
export async function streamChatMessage(
  request: ChatRequest,
  onEvent: (event: { type: string; [key: string]: unknown }) => void,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `Chat error: ${res.status}`, res.status);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new ApiError("No response body", 0);

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const event = JSON.parse(line.slice(6));
          onEvent(event);
        } catch {
          // skip malformed events
        }
      }
    }
  }
}

export async function getChatHistory(conversationId: string) {
  return apiFetch<{ conversation_id: string; messages: unknown[]; count: number }>(
    `/chat/history/${conversationId}`,
  );
}

// --- Document API ---

export async function searchDocuments(query: string, k = 10) {
  return apiFetch<{ query: string; results: unknown[]; count: number }>(
    `/documents/search?q=${encodeURIComponent(query)}&k=${k}`,
  );
}

export async function getDocumentStats() {
  return apiFetch<{ total_chunks: number; table: string; updated_at: string }>(
    "/documents/stats",
  );
}

// --- Dashboard API ---

export async function getDashboardStats() {
  return apiFetch<DashboardStats>("/dashboard/stats");
}

export async function getDashboardQueries(limit = 20) {
  return apiFetch<QueryLogEntry[]>(`/dashboard/queries?limit=${limit}`);
}

export async function getDashboardIngestions(limit = 20) {
  return apiFetch<IngestionLogEntry[]>(`/dashboard/ingestions?limit=${limit}`);
}

export async function getRetrievalQuality(days = 7) {
  return apiFetch<RetrievalQuality>(`/dashboard/retrieval-quality?days=${days}`);
}

export async function getAgentBehavior(days = 7) {
  return apiFetch<AgentBehavior>(`/dashboard/agent-behavior?days=${days}`);
}

export async function getDashboardSessions(limit = 20, offset = 0) {
  return apiFetch<SessionSummary[]>(
    `/dashboard/sessions?limit=${limit}&offset=${offset}`,
  );
}

export async function getDashboardSessionMessages(sessionId: string) {
  return apiFetch<SessionMessageDetail[]>(
    `/dashboard/sessions/${sessionId}/messages`,
  );
}

// --- Upload API ---

export function uploadFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<FileUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const formData = new FormData();
    formData.append("file", file);

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new ApiError(body.detail || `Upload failed: ${xhr.status}`, xhr.status));
        } catch {
          reject(new ApiError(`Upload failed: ${xhr.status}`, xhr.status));
        }
      }
    });

    xhr.addEventListener("error", () =>
      reject(new ApiError("Network error — check your connection", 0)),
    );
    xhr.addEventListener("abort", () =>
      reject(new ApiError("Upload aborted", 0)),
    );

    xhr.open("POST", `${API_BASE}/upload`);
    xhr.send(formData);
  });
}

/** Upload file with SSE streaming of pipeline progress steps. */
export async function uploadFileStreaming(
  file: File,
  onEvent: (event: { type: string; [key: string]: unknown }) => void,
) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload/stream`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail || `Upload failed: ${res.status}`, res.status);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new ApiError("No response body", 0);

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch {
          // skip malformed events
        }
      }
    }
  }
}
