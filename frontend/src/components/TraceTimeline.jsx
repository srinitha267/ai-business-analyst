import React from 'react'

export default function TraceTimeline({ trace }) {
  return (
    <section className="card">
      <h2>Full trace — every answer is auditable</h2>
      <ol className="trace">
        {trace.steps.map(s => (
          <li key={s.step}>
            <div className="step-num">{s.step}</div>
            <div className="step-body">
              <div className="step-name">{s.name}</div>
              <div className="step-val">
                {Array.isArray(s.value) ? s.value.join(', ')
                  : typeof s.value === 'object' && s.value !== null
                    ? JSON.stringify(s.value)
                    : String(s.value ?? '—')}
              </div>
              {s.detail && <div className="step-detail">{s.detail}</div>}
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}