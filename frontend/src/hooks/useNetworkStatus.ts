import * as React from "react";
import { API_BASE_URL } from "../services/api";

const PROBE_INTERVAL_MS = 15_000;
const PROBE_TIMEOUT_MS = 12_000;
const API_RECENT_GRACE_MS = 20_000;

type Listener = () => void;

const listeners = new Set<Listener>();
let currentOnline: boolean =
  typeof navigator !== "undefined" ? navigator.onLine : true;
let lastApiSuccessAt = 0;
let inFlightProbe: Promise<boolean> | null = null;
let intervalId: number | null = null;
let listenersAttached = false;

function notifyListeners() {
  listeners.forEach((listener) => listener());
}

function setOnlineState(next: boolean) {
  if (currentOnline === next) return;
  currentOnline = next;
  notifyListeners();
}

/**
 * Sinaliza ao monitor que uma chamada real à API acabou de responder,
 * evitando falso estado "Offline" enquanto o sistema opera normalmente.
 */
export function notifyNetworkReachable() {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return;
  }
  lastApiSuccessAt = Date.now();
  setOnlineState(true);
}

function resolveProbeUrls(): string[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    const normalizedBase = apiUrl.href.replace(/\/+$/, "");
    return Array.from(
      new Set([`${normalizedBase}/health`, `${apiUrl.origin}/health`])
    );
  } catch {
    return [];
  }
}

async function probeUrl(url: string, signal: AbortSignal): Promise<boolean> {
  try {
    const response = await fetch(url, {
      method: "GET",
      mode: "cors",
      cache: "no-store",
      signal,
    });
    return response.ok;
  } catch (error) {
    if (signal.aborted || (error instanceof DOMException && error.name === "AbortError")) {
      return false;
    }
    // Se CORS de um proxy intermediário bloquear /health mas o servidor responder HTTP,
    // no-cors confirma conectividade real (enquanto erro de DNS/TCP continua lançando TypeError).
    try {
      const opaqueResponse = await fetch(url, {
        method: "GET",
        mode: "no-cors",
        cache: "no-store",
        signal,
      });
      return opaqueResponse.type === "opaque" || opaqueResponse.ok;
    } catch {
      return false;
    }
  }
}

/**
 * Executa uma verificação real de conectividade de rede (sem mocks).
 * Quando `navigator.onLine` é falso, retorna falso imediatamente.
 */
export async function checkNetworkConnectivity(): Promise<boolean> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    lastApiSuccessAt = 0;
    setOnlineState(false);
    return false;
  }

  if (
    lastApiSuccessAt > 0 &&
    Date.now() - lastApiSuccessAt < API_RECENT_GRACE_MS
  ) {
    setOnlineState(true);
    return true;
  }

  if (typeof fetch === "undefined") {
    return currentOnline;
  }

  if (inFlightProbe) {
    return inFlightProbe;
  }

  const probeUrls = resolveProbeUrls();
  if (probeUrls.length === 0) {
    return currentOnline;
  }

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

  inFlightProbe = (async () => {
    for (const url of probeUrls) {
      if (controller.signal.aborted) break;
      const ok = await probeUrl(url, controller.signal);
      if (ok) {
        lastApiSuccessAt = Date.now();
        setOnlineState(true);
        return true;
      }
    }
    setOnlineState(false);
    return false;
  })().finally(() => {
    window.clearTimeout(timeoutId);
    inFlightProbe = null;
  });

  return inFlightProbe;
}

const handleBrowserOffline = () => {
  lastApiSuccessAt = 0;
  setOnlineState(false);
};

const handleBrowserOnline = () => {
  setOnlineState(true);
  void checkNetworkConnectivity();
};

const handleVisibilityOrFocus = () => {
  if (typeof document !== "undefined" && document.visibilityState === "hidden") {
    return;
  }
  void checkNetworkConnectivity();
};

const handleApiReachable = () => {
  notifyNetworkReachable();
};

function startMonitoring() {
  if (typeof window === "undefined" || listenersAttached) return;

  listenersAttached = true;
  currentOnline = typeof navigator !== "undefined" ? navigator.onLine : true;

  window.addEventListener("online", handleBrowserOnline);
  window.addEventListener("offline", handleBrowserOffline);
  window.addEventListener("focus", handleVisibilityOrFocus);
  window.addEventListener("kultiva-api-reachable", handleApiReachable);
  document.addEventListener("visibilitychange", handleVisibilityOrFocus);

  intervalId = window.setInterval(() => {
    if (document.visibilityState === "hidden") return;
    void checkNetworkConnectivity();
  }, PROBE_INTERVAL_MS);

  void checkNetworkConnectivity();
}

function stopMonitoring() {
  if (typeof window === "undefined" || !listenersAttached) return;

  listenersAttached = false;
  window.removeEventListener("online", handleBrowserOnline);
  window.removeEventListener("offline", handleBrowserOffline);
  window.removeEventListener("focus", handleVisibilityOrFocus);
  window.removeEventListener("kultiva-api-reachable", handleApiReachable);
  document.removeEventListener("visibilitychange", handleVisibilityOrFocus);

  if (intervalId !== null) {
    window.clearInterval(intervalId);
    intervalId = null;
  }
}

function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  if (listeners.size === 1) {
    startMonitoring();
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      stopMonitoring();
    }
  };
}

function getSnapshot(): boolean {
  return currentOnline;
}

function getServerSnapshot(): boolean {
  return true;
}

/**
 * Hook que reflete o estado real de acesso à rede do usuário,
 * combinando eventos do navegador com verificação ativa de conectividade.
 */
export function useNetworkStatus(): boolean {
  return React.useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

