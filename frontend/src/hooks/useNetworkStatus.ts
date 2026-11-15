import * as React from "react";
import { API_BASE_URL } from "../services/api";

const PROBE_INTERVAL_MS = 15_000;
const PROBE_TIMEOUT_MS = 4_000;
const EXTERNAL_PROBE_URL = "https://www.gstatic.com/generate_204";

type Listener = () => void;

const listeners = new Set<Listener>();
let currentOnline: boolean =
  typeof navigator !== "undefined" ? navigator.onLine : true;
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

function resolveProbeTarget(): { url: string; mode: RequestMode } {
  if (typeof window === "undefined") {
    return { url: EXTERNAL_PROBE_URL, mode: "no-cors" };
  }

  try {
    const apiUrl = new URL(API_BASE_URL, window.location.origin);
    const isLocalHost =
      apiUrl.hostname === "localhost" ||
      apiUrl.hostname === "127.0.0.1" ||
      apiUrl.hostname === "::1";

    if (isLocalHost) {
      return { url: EXTERNAL_PROBE_URL, mode: "no-cors" };
    }

    return { url: `${apiUrl.origin}/health`, mode: "cors" };
  } catch {
    return { url: EXTERNAL_PROBE_URL, mode: "no-cors" };
  }
}

/**
 * Executa uma verificação real de conectividade de rede (sem mocks).
 * Quando `navigator.onLine` é falso, retorna falso imediatamente.
 */
export async function checkNetworkConnectivity(): Promise<boolean> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    setOnlineState(false);
    return false;
  }

  if (typeof fetch === "undefined") {
    return currentOnline;
  }

  if (inFlightProbe) {
    return inFlightProbe;
  }

  const { url, mode } = resolveProbeTarget();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS);

  inFlightProbe = fetch(url, {
    method: "GET",
    mode,
    cache: "no-store",
    signal: controller.signal,
  })
    .then((response) => {
      const reachable = response.type === "opaque" || response.ok;
      setOnlineState(reachable);
      return reachable;
    })
    .catch(() => {
      setOnlineState(false);
      return false;
    })
    .finally(() => {
      window.clearTimeout(timeoutId);
      inFlightProbe = null;
    });

  return inFlightProbe;
}

const handleBrowserOffline = () => {
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

function startMonitoring() {
  if (typeof window === "undefined" || listenersAttached) return;

  listenersAttached = true;
  currentOnline = typeof navigator !== "undefined" ? navigator.onLine : true;

  window.addEventListener("online", handleBrowserOnline);
  window.addEventListener("offline", handleBrowserOffline);
  window.addEventListener("focus", handleVisibilityOrFocus);
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

