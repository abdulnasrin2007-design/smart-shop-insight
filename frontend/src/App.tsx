import { useEffect, useState, useCallback } from "react";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import { LayoutDashboard, TrendingUp, Package, Boxes, Upload, Lightbulb } from "lucide-react";
import { api, inr } from "./api";

const NAV = [["Overview", LayoutDashboard], ["Sales Analytics", TrendingUp], ["Products", Package],
  ["Inventory", Boxes], ["Data Import", Upload], ["Business Insights", Lightbulb]] as const;
const STATUS: Record<string, string> = { healthy: "✓ Healthy", low: "⚠ Low stock", out_of_stock: "✕ Out of stock" };
const card = "rounded-xl border border-stone-200 bg-white p-4 shadow-sm";

function useData<T>(path: string) {
  const [data, setData] = useState<T | null>(null); const [error, setError] = useState(""); const [n, setN] = useState(0);
  useEffect(() => { setError(""); api<T>(path).then(setData).catch(e => setError(e.message)); }, [path, n]);
  return { data, error, reload: () => setN(x => x + 1) };
}
const Msg = ({ error }: { error: string }) => error ? <p role="alert" className="rounded bg-red-50 p-3 text-red-700">{error}</p> : <p className="text-stone-500">Loading…</p>;

export default function App() {
  const [tab, setTab] = useState("Overview");
  const [days, setDays] = useState(30); const [custom, setCustom] = useState({ start: "", end: "" });
  const [category, setCategory] = useState("");
  const meta = useData<any>("/meta");
  const range = custom.start && custom.end ? `start=${custom.start}&end=${custom.end}` : `days=${days}`;
  const q = `${range}${category ? `&category=${encodeURIComponent(category)}` : ""}`;
  return (
    <div className="min-h-screen md:flex">
      <nav aria-label="Main" className="flex gap-1 overflow-x-auto bg-forest p-2 text-white md:w-56 md:flex-col md:p-4">
        <h1 className="hidden px-2 pb-4 text-lg font-bold md:block">Smart Shop Insights</h1>
        {NAV.map(([name, Icon]) => (
          <button key={name} onClick={() => setTab(name)} aria-current={tab === name ? "page" : undefined}
            className={`flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-left text-sm transition ${tab === name ? "bg-white/20 font-semibold" : "hover:bg-white/10"}`}>
            <Icon size={16} />{name}</button>))}
      </nav>
      <main className="flex-1 space-y-4 p-4 md:p-6">
        <header className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">{meta.data?.store_name ?? "Store"}</h2>
          {meta.data?.is_demo_data && <span className="rounded-full bg-amber-100 px-3 py-1 text-xs text-amber-900">Synthetic demo data</span>}
          <div className="ml-auto flex flex-wrap items-center gap-2 text-sm">
            {[7, 30, 90].map(d => <button key={d} onClick={() => { setDays(d); setCustom({ start: "", end: "" }); }}
              className={`rounded border px-2 py-1 ${!custom.start && days === d ? "bg-forest text-white" : "bg-white"}`}>Last {d} days</button>)}
            <input aria-label="Start date" type="date" value={custom.start} onChange={e => setCustom({ ...custom, start: e.target.value })} className="rounded border px-1 py-1" />
            <input aria-label="End date" type="date" value={custom.end} onChange={e => setCustom({ ...custom, end: e.target.value })} className="rounded border px-1 py-1" />
            <select aria-label="Category" value={category} onChange={e => setCategory(e.target.value)} className="rounded border px-1 py-1">
              <option value="">All categories</option>{meta.data?.categories.map((c: string) => <option key={c}>{c}</option>)}</select>
          </div>
        </header>
        {tab === "Overview" && <Overview q={q} />}
        {tab === "Sales Analytics" && <Sales q={q} />}
        {tab === "Products" && <Products q={q} />}
        {tab === "Inventory" && <Inventory />}
        {tab === "Data Import" && <ImportPage onDone={meta.reload} isDemo={!!meta.data?.is_demo_data} />}
        {tab === "Business Insights" && <Insights q={q} />}
      </main>
    </div>);
}

function Overview({ q }: { q: string }) {
  const { data: d, error } = useData<any>(`/dashboard?${q}`);
  if (!d) return <Msg error={error} />;
  const k = d.kpis, ch = (v: number | null) => v == null ? "No comparison available" : `${v > 0 ? "▲" : v < 0 ? "▼" : ""} ${Math.abs(v)}% vs previous period`;
  const cards = [["Total Revenue", inr(k.revenue), d.changes.revenue], ["Gross Profit (before expenses)", inr(k.gross_profit), d.changes.gross_profit],
    ["Units Sold", k.units_sold.toLocaleString("en-IN"), d.changes.units_sold], ["Transactions", k.transactions, d.changes.transactions],
    ["Gross Profit Margin", k.gross_margin_pct == null ? "—" : k.gross_margin_pct + "%", null]] as const;
  return (<div className="space-y-4">
    <p className="text-sm text-stone-500">Showing {d.period.start} to {d.period.end}</p>
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">{cards.map(([t, v, c]) => <div key={t} className={card}><p className="text-xs text-stone-500">{t}</p><p className="text-xl font-bold">{v}</p>{c !== null && <p className="text-xs text-stone-500">{ch(c)}</p>}</div>)}</div>
    {d.daily.length === 0 ? <p className={card}>No sales match these filters.</p> : <>
    <div className={card}><h3 className="mb-2 font-semibold">Daily revenue and gross profit (₹)</h3><ResponsiveContainer height={260}><LineChart data={d.daily}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="period" fontSize={11} /><YAxis fontSize={11} tickFormatter={v => "₹" + v / 1000 + "k"} /><Tooltip formatter={(v: number) => inr(v)} /><Legend /><Line dataKey="revenue" name="Revenue" stroke="#0f6b4a" dot={false} /><Line dataKey="gross_profit" name="Gross profit" stroke="#d97706" dot={false} /></LineChart></ResponsiveContainer></div>
    <div className="grid gap-4 lg:grid-cols-2">
      <div className={card}><h3 className="mb-2 font-semibold">Revenue by category (₹)</h3><ResponsiveContainer height={240}><BarChart data={d.categories}><XAxis dataKey="category" fontSize={10} /><YAxis fontSize={11} /><Tooltip formatter={(v: number) => inr(v)} /><Bar dataKey="revenue" name="Revenue" fill="#0f6b4a" /></BarChart></ResponsiveContainer></div>
      <div className={card}><h3 className="mb-2 font-semibold">Needs attention (stock)</h3>{d.attention.length === 0 ? <p>All products are above reorder level.</p> : <ul className="space-y-1 text-sm">{d.attention.map((i: any) => <li key={i.id}>{STATUS[i.status]} — {i.name}: {i.stock} {i.unit} (reorder at {i.reorder_level})</li>)}</ul>}</div>
      <TopList title="Top 5 by revenue" rows={d.top_by_revenue} field="revenue" /><TopList title="Top 5 by gross profit" rows={d.top_by_profit} field="gross_profit" /></div></>}
  </div>);
}
const TopList = ({ title, rows, field }: any) => <div className={card}><h3 className="mb-2 font-semibold">{title}</h3><ol className="list-decimal pl-5 text-sm">{rows.map((r: any) => <li key={r.product_id}>{r.product_name} — {inr(r[field])}</li>)}</ol></div>;

function Sales({ q }: { q: string }) {
  const [freq, setFreq] = useState("D"); const [search, setSearch] = useState(""); const [page, setPage] = useState(1);
  const ts = useData<any[]>(`/sales/timeseries?freq=${freq}&${q}`);
  const tx = useData<any>(`/transactions?${q}&search=${encodeURIComponent(search)}&page=${page}`);
  return (<div className="space-y-4">
    <div className={card}><div className="mb-2 flex gap-2">{[["D", "Daily"], ["W", "Weekly"], ["M", "Monthly"]].map(([f, l]) => <button key={f} onClick={() => setFreq(f)} className={`rounded border px-2 py-1 text-sm ${freq === f ? "bg-forest text-white" : ""}`}>{l}</button>)}</div>
      {ts.data ? <ResponsiveContainer height={260}><BarChart data={ts.data}><XAxis dataKey="period" fontSize={11} /><YAxis fontSize={11} /><Tooltip formatter={(v: number) => inr(v)} /><Legend /><Bar dataKey="revenue" name="Revenue" fill="#0f6b4a" /><Bar dataKey="gross_profit" name="Gross profit" fill="#d97706" /></BarChart></ResponsiveContainer> : <Msg error={ts.error} />}</div>
    <div className={card}><input aria-label="Search transactions" placeholder="Search product or transaction ID" value={search} onChange={e => { setSearch(e.target.value); setPage(1); }} className="mb-2 w-full rounded border p-2 text-sm" />
      {tx.data ? (tx.data.rows.length === 0 ? <p>No transactions match your filters.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th>Date</th><th>Txn</th><th>Product</th><th>Qty</th><th>Revenue</th><th>Gross profit</th></tr></thead><tbody>{tx.data.rows.map((r: any) => <tr key={r.line_id} className="border-b"><td>{r.sold_at}</td><td>{r.transaction_id}</td><td>{r.product_name}</td><td>{r.quantity}</td><td>{inr(r.revenue)}</td><td>{inr(r.profit)}</td></tr>)}</tbody></table></div>) : <Msg error={tx.error} />}
      <div className="mt-2 flex items-center gap-2 text-sm"><button disabled={page === 1} onClick={() => setPage(page - 1)} className="rounded border px-2 disabled:opacity-40">Prev</button>Page {page} of {Math.max(1, Math.ceil((tx.data?.total ?? 0) / 20))}<button disabled={page * 20 >= (tx.data?.total ?? 0)} onClick={() => setPage(page + 1)} className="rounded border px-2 disabled:opacity-40">Next</button></div></div></div>);
}

function Products({ q }: { q: string }) {
  const { data, error } = useData<any[]>(`/products?${q}`); const [s, setS] = useState(""); const [sort, setSort] = useState("revenue");
  if (!data) return <Msg error={error} />;
  const rows = data.filter(p => p.name.toLowerCase().includes(s.toLowerCase())).sort((a, b) => b[sort] - a[sort]);
  return (<div className={card}><div className="mb-2 flex gap-2 text-sm"><input aria-label="Search products" placeholder="Search products" value={s} onChange={e => setS(e.target.value)} className="flex-1 rounded border p-2" />
    <select aria-label="Sort by" value={sort} onChange={e => setSort(e.target.value)} className="rounded border"><option value="revenue">Highest revenue</option><option value="units_sold">Best-selling (units)</option><option value="gross_profit">Highest gross profit</option></select></div>
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th>Product</th><th>Category</th><th>Price</th><th>Cost</th><th>Units</th><th>Revenue</th><th>Gross profit</th><th>Margin</th><th>Stock</th></tr></thead>
      <tbody>{rows.map(p => <tr key={p.id} className="border-b"><td>{p.name}</td><td>{p.category}</td><td>{inr(p.selling_price)}</td><td>{inr(p.unit_cost)}</td><td>{p.units_sold}</td><td>{inr(p.revenue)}</td><td>{inr(p.gross_profit)}</td><td>{p.margin_pct == null ? "—" : p.margin_pct + "%"}</td><td>{p.stock}</td></tr>)}</tbody></table></div></div>);
}

function Inventory() {
  const [cover, setCover] = useState(14); const { data, error, reload } = useData<any[]>(`/inventory?cover_days=${cover}`);
  const [msg, setMsg] = useState("");
  async function save(id: string, stock: string, level: string) {
    try { await api(`/inventory/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stock: Number(stock), reorder_level: Number(level) }) });
      setMsg("Saved."); reload(); } catch (e: any) { setMsg("Not saved: " + e.message); } }
  if (!data) return <Msg error={error} />;
  return (<div className={card}>
    <p className="mb-2 text-sm text-stone-600">Low = stock ≤ reorder level. Out = 0. Suggested reorder = stock needed to cover <input aria-label="Cover days" type="number" min={1} value={cover} onChange={e => setCover(Number(e.target.value) || 14)} className="w-14 rounded border px-1" /> days at the last-30-day average — an estimate, not guaranteed demand. Imported sales do not change stock automatically; adjust stock here.</p>
    {msg && <p role="status" className="mb-2 text-sm">{msg}</p>}
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b"><th>Product</th><th>Status</th><th>Stock</th><th>Reorder level</th><th>Unit cost</th><th>Suggested order</th><th></th></tr></thead><tbody>
      {data.map(i => <Row key={i.id} i={i} save={save} />)}</tbody></table></div></div>);
}
function Row({ i, save }: any) {
  const [s, setS] = useState(String(i.stock)); const [l, setL] = useState(String(i.reorder_level));
  return <tr className="border-b"><td>{i.name}<br /><span className="text-xs text-stone-500">{i.category}</span></td><td>{STATUS[i.status]}</td>
    <td><input aria-label={`Stock for ${i.name}`} type="number" min={0} value={s} onChange={e => setS(e.target.value)} className="w-16 rounded border px-1" /> {i.unit}</td>
    <td><input aria-label={`Reorder level for ${i.name}`} type="number" min={0} value={l} onChange={e => setL(e.target.value)} className="w-16 rounded border px-1" /></td>
    <td>{inr(i.unit_cost)}</td><td>{i.suggested_reorder ?? "No sales history"}</td><td><button onClick={() => save(i.id, s, l)} className="rounded bg-forest px-2 py-1 text-white">Save</button></td></tr>;
}

function ImportPage({ onDone, isDemo }: { onDone: () => void; isDemo: boolean }) {
  const [file, setFile] = useState<File | null>(null); const [res, setRes] = useState<any>(null); const [done, setDone] = useState<any>(null); const [err, setErr] = useState("");
  const send = async (path: string) => { const f = new FormData(); f.append("file", file!); return api(path, { method: "POST", body: f }); };
  return (<div className={`${card} space-y-3`}>
    <p className="text-sm">Upload a sales CSV. Rows with a line_id already stored are skipped as duplicates. <a className="underline" href="/api/import/template">Download template</a></p>
    <input aria-label="CSV file" type="file" accept=".csv" onChange={e => { setFile(e.target.files?.[0] ?? null); setRes(null); setDone(null); setErr(""); }} />
    <button disabled={!file} onClick={() => send("/import/validate").then(setRes).catch(e => setErr(e.message))} className="ml-2 rounded border px-2 py-1 disabled:opacity-40">Check file</button>
    {err && <p role="alert" className="text-red-700">{err}</p>}
    {res && <div className="text-sm"><p>{res.total_rows} rows: <b>{res.accepted}</b> ready, <b>{res.rejected}</b> with errors, <b>{res.duplicates}</b> duplicates.</p>
      {res.errors.map((e: any, n: number) => <p key={n} className="text-red-700">Row {e.row} ({e.field}): {e.message}</p>)}
      <button disabled={res.accepted === 0} onClick={() => send("/import/commit").then(r => { setDone(r); setRes(null); onDone(); }).catch(e => setErr(e.message))} className="mt-2 rounded bg-forest px-3 py-1 text-white disabled:opacity-40">Import {res.accepted} rows</button></div>}
    {done && <p role="status">Import complete: {done.accepted} accepted, {done.rejected} rejected, {done.duplicates} duplicates.</p>}
    {isDemo && <button onClick={async () => { if (confirm("Reset demo data? Your changes will be lost.")) { try { await api("/demo/reset", { method: "POST" }); onDone(); setDone({ accepted: 0, rejected: 0, duplicates: 0 }); } catch (e: any) { setErr(e.message); } } }} className="block rounded border px-2 py-1 text-sm">Reset demo data</button>}
    {!isDemo && <button onClick={async () => { if (confirm("Replace everything with fresh demo data?")) { await api("/demo/reset", { method: "POST" }); onDone(); } }} className="block rounded border px-2 py-1 text-sm">Reset to demo data</button>}
  </div>);
}

function Insights({ q }: { q: string }) {
  const { data, error } = useData<any[]>(`/insights?${q}`);
  if (!data) return <Msg error={error} />;
  return <div className="space-y-3"><p className="text-sm text-stone-500">Rule-based insights calculated from your sales and stock numbers.</p>{data.map((i, n) => <div key={n} className={card}><h3 className="font-semibold">{i.title}</h3><p className="text-sm">{i.detail}</p><p className="text-sm text-stone-500">Why it matters: {i.why}</p><p className="text-sm">Next step: {i.action}</p></div>)}</div>;
}
