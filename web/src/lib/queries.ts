import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  CheckResult,
  CheckRow,
  Health,
  Incident,
  Kind,
  Product,
  ProductDetail,
  ProductInput,
  ProductSummary,
  Range,
  SeriesPoint,
  SettingsResponse,
  Summary,
} from "./types";

export const REFRESH_MS = 30_000;

export const keys = {
  products: (kind?: Kind) => ["products", kind ?? "all"] as const,
  summary: ["summary"] as const,
  product: (id: string) => ["product", id] as const,
  series: (id: string, range: Range) => ["series", id, range] as const,
  checks: (id: string) => ["checks", id] as const,
  productIncidents: (id: string) => ["incidents", "product", id] as const,
  incidents: (state: "open" | "all") => ["incidents", "feed", state] as const,
  settings: ["settings"] as const,
  health: ["health"] as const,
};

export function useProducts(kind?: Kind) {
  return useQuery({
    queryKey: keys.products(kind),
    queryFn: () => api<ProductSummary[]>(kind ? `/products?kind=${kind}` : "/products"),
    refetchInterval: REFRESH_MS,
  });
}

export function useSummary() {
  return useQuery({ queryKey: keys.summary, queryFn: () => api<Summary>("/summary"), refetchInterval: REFRESH_MS });
}

export function useProduct(id: string, enabled = true) {
  return useQuery({
    queryKey: keys.product(id),
    queryFn: () => api<ProductDetail>(`/products/${id}`),
    refetchInterval: REFRESH_MS,
    enabled: enabled && id !== "",
  });
}

export function useSeries(id: string, range: Range) {
  return useQuery({
    queryKey: keys.series(id, range),
    queryFn: () => api<{ range: Range; points: SeriesPoint[] }>(`/products/${id}/series?range=${range}`),
    refetchInterval: range === "24h" ? REFRESH_MS : 5 * 60_000,
  });
}

export function useChecks(id: string) {
  return useQuery({
    queryKey: keys.checks(id),
    queryFn: () => api<CheckRow[]>(`/products/${id}/checks?limit=20`),
    refetchInterval: REFRESH_MS,
  });
}

export function useProductIncidents(id: string) {
  return useQuery({
    queryKey: keys.productIncidents(id),
    queryFn: () => api<Incident[]>(`/products/${id}/incidents?limit=20`),
  });
}

export function useIncidentFeed(state: "open" | "all") {
  return useQuery({
    queryKey: keys.incidents(state),
    queryFn: () => api<Incident[]>(`/incidents?state=${state}&limit=50`),
    refetchInterval: REFRESH_MS,
  });
}

export function useSettings() {
  return useQuery({ queryKey: keys.settings, queryFn: () => api<SettingsResponse>("/settings") });
}

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: () => api<Health>("/health"), refetchInterval: 60_000 });
}

/** After any write, refresh everything that shows product state. */
function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "health" });
}

export function useCreateProduct() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (input: ProductInput) => api<Product>("/products", { method: "POST", body: input }),
    onSuccess: invalidate,
  });
}

export function useUpdateProduct(id: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (input: Partial<ProductInput>) => api<Product>(`/products/${id}`, { method: "PATCH", body: input }),
    onSuccess: invalidate,
  });
}

export function useDeleteProduct(id: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: () => api<null>(`/products/${id}`, { method: "DELETE" }),
    onSuccess: invalidate,
  });
}

export function usePauseResume(id: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (action: "pause" | "resume") => api<Product>(`/products/${id}/${action}`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function useTestNow(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<CheckResult>(`/products/${id}/test`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.checks(id) }),
  });
}

export function useAcknowledge(productId: string) {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (incidentId: string) =>
      api<Incident>(`/products/${productId}/incidents/${encodeURIComponent(incidentId)}/ack`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function useTestNotification() {
  return useMutation({ mutationFn: () => api<{ queued: boolean }>("/notifications/test", { method: "POST" }) });
}

export function useDemo() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (action: "break" | "fix") => api<{ healthy: boolean }>(`/demo/${action}`, { method: "POST" }),
    onSuccess: invalidate,
  });
}

export function usePatchSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<SettingsResponse["settings"]>) =>
      api<SettingsResponse["settings"]>("/settings", { method: "PATCH", body: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.settings }),
  });
}
