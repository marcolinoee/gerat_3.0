/**
 * Relative API client (/api/v1) with in-memory JWT Access Token and HttpOnly Refresh Cookie.
 */

const API_BASE = "/api/v1";

let accessTokenMemory: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export function setAccessToken(token: string | null) {
  accessTokenMemory = token;
}

export function getAccessToken(): string | null {
  return accessTokenMemory;
}

async function tryRefreshToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) {
          accessTokenMemory = null;
          return null;
        }
        const data = await res.json();
        accessTokenMemory = data.access_token ?? null;
        return accessTokenMemory;
      })
      .catch(() => {
        accessTokenMemory = null;
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  retryOn401 = true
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessTokenMemory) {
    headers.set("Authorization", `Bearer ${accessTokenMemory}`);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && retryOn401 && !path.startsWith("/auth/")) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      return apiFetch<T>(path, options, false);
    }
  }

  if (!res.ok) {
    let msg = `Erro HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      if (typeof errBody.detail === "string") {
        msg = errBody.detail;
      } else if (Array.isArray(errBody.detail) && errBody.detail[0]?.msg) {
        msg = errBody.detail[0].msg;
      }
    } catch {
      // ignore json parse errors
    }
    throw new ApiError(res.status, msg);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function apiDownloadBlob(path: string, filename: string): Promise<void> {
  const headers = new Headers();
  if (accessTokenMemory) {
    headers.set("Authorization", `Bearer ${accessTokenMemory}`);
  }
  let res = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers,
    credentials: "include",
  });
  if (res.status === 401) {
    const newToken = await tryRefreshToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetch(`${API_BASE}${path}`, {
        method: "GET",
        headers,
        credentials: "include",
      });
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, `Falha ao baixar arquivo (HTTP ${res.status})`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
