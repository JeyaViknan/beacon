// The JWT lives in localStorage. On iOS the installed home-screen app has its own storage,
// separate from Safari, so you log in once inside the installed app.

const TOKEN_KEY = "beacon.token";
const EXPIRES_KEY = "beacon.expiresAt";
const listeners = new Set<() => void>();

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getToken(now: Date = new Date()): string | null {
  const token = safeGet(TOKEN_KEY);
  const expires = safeGet(EXPIRES_KEY);
  if (!token || !expires) return null;
  if (new Date(expires).getTime() <= now.getTime()) return null;
  return token;
}

export function setToken(token: string, expiresAt: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(EXPIRES_KEY, expiresAt);
  } finally {
    listeners.forEach((fn) => fn());
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EXPIRES_KEY);
  } finally {
    listeners.forEach((fn) => fn());
  }
}

export function onAuthChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
