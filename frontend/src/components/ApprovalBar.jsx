import React, { useState } from 'react'
import { approve } from '../api'

export default function ApprovalBar({ answerId, approval }) {
  const [status, setStatus] = useState(approval?.status || 'pending')
  const [note, setNote] = useState('')

  async function decide(decision) {
    const res = await approve(answerId, decision, note)
    setStatus(res.approval.status)
  }

  return (
    <section className="card approval">
      <h2>The AI recommends. A person decides.</h2>
      <p>Current status: <strong>{status}</strong></p>
      <input
        type="text"
        placeholder="Optional note for the audit trail"
        value={note}
        onChange={e => setNote(e.target.value)}
      />
      <div className="row">
        <button className="ok" onClick={() => decide('approve')}>Approve</button>
        <button className="bad" onClick={() => decide('reject')}>Reject</button>
        <button className="more" onClick={() => decide('request_more')}>Request more analysis</button>
      </div>
    </section>
  )
}