const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";
export class ApiError extends Error {
  constructor(public code: string, message: string, public retryable: boolean) { super(message); }
}
export async function api<T>(path: string, body?: unknown, method?: "DELETE"): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method: method || (body === undefined ? "GET" : "POST"),
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(55000),
    });
  } catch {
    throw new ApiError("CONNECTION_FAILED", "Cannot reach the API. Check the local server and retry.", true);
  }
  const data = await response.json();
  if (!response.ok) throw new ApiError(data.error?.code || "API_ERROR", data.error?.message || "Request failed.", data.error?.retryable ?? true);
  return data as T;
}
export function mediaUrl(path: string) { return new URL(path, BASE).href; }
export function money(cents: number) { return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(cents / 100); }
