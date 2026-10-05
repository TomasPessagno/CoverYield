import type { components } from "./api-types";

type Schemas = components["schemas"];
export type Contract = Schemas["Contract"];
export type Opportunity = Schemas["Opportunity"];
export type ScreenerResponse = Schemas["ScreenerResponse"];
export type OpportunitiesRequest = Schemas["OpportunitiesRequest"];
export type OpportunitiesResponse = Schemas["OpportunitiesResponse"];
export type ScanTickerResponse = Schemas["ScanTickerResponse"];
export type TickerMatch = Schemas["TickerMatch"];
export type UniverseTicker = Schemas["UniverseTicker"];
export type Weights = Schemas["Weights"];

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    let detail = res.statusText || "Request failed";
    try {
      const body: unknown = await res.json();
      if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // keep the status text
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  universe: () => request<UniverseTicker[]>("/universe"),
  search: (q: string, signal?: AbortSignal) =>
    request<TickerMatch[]>(`/search?q=${encodeURIComponent(q)}`, { signal }),
  /** ``null`` days mean no limit on that side of the expiry window. */
  screener: (ticker: string, minDays: number | null, maxDays: number | null) => {
    const params = new URLSearchParams();
    if (minDays !== null) params.set("min_days", String(minDays));
    if (maxDays !== null) params.set("max_days", String(maxDays));
    const qs = params.size ? `?${params}` : "";
    return request<ScreenerResponse>(`/screener/${encodeURIComponent(ticker)}${qs}`);
  },
  scanTicker: (ticker: string) =>
    request<ScanTickerResponse>(`/scan/${encodeURIComponent(ticker)}`, { method: "POST" }),
  opportunities: (body: OpportunitiesRequest, signal?: AbortSignal) =>
    request<OpportunitiesResponse>("/opportunities", {
      method: "POST",
      body: JSON.stringify(body),
      signal,
    }),
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof TypeError) return "Can't reach the API. Is the backend running on port 8000?";
  return e instanceof Error ? e.message : String(e);
}
