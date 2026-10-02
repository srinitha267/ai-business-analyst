import React from 'react'

export default function AnswerCard({ answer, explanation, recommendation, confidence }) {
  return (
    <section className="card answer">
      <div className="badge">Confidence: {confidence}</div>
      <h2>Answer</h2>
      <p className="headline">{answer}</p>
      <h3>AI explanation</h3>
      <p>{explanation}</p>
      <h3>Recommendation</h3>
      <p className="reco">{recommendation}</p>
    </section>
  )
}