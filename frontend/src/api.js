const BASE = 'http://localhost:8000'

export async function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  const r = await fetch(`${BASE}/upload`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error((await r.json()).detail || 'Upload failed')
  return r.json()
}

export async function ask(dataset_id, question) {
  const r = await fetch(`${BASE}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id, question })
  })
  return r.json()
}

export async function approve(answer_id, decision, note) {
  const r = await fetch(`${BASE}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer_id, decision, note })
  })
  return r.json()
}