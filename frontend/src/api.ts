// Thin wrapper around fetch with friendly error messages.
export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch("/api" + path, init); }
  catch { throw new Error("Cannot reach the backend. Is it running on port 8000?"); }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : "The request could not be completed.");
  }
  return res.json();
}
export const inr = (n: number | null | undefined) =>
  n == null ? "—" : "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
