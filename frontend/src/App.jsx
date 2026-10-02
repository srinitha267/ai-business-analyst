import React, { useState } from 'react'
import { uploadFile, ask } from './api'
import Upload from './components/Upload'
import QuestionBox from './components/QuestionBox'
import AnswerCard from './components/AnswerCard'
import EvidencePanel from './components/EvidencePanel'
import ChartView from './components/ChartView'
import TraceTimeline from './components/TraceTimeline'
import ApprovalBar from './components/ApprovalBar'
import InsufficientEvidence from './components/InsufficientEvidence'

export default function App() {
  const [dataset, setDataset] = useState(null)
  const [question, setQuestion] = useState('')
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleUpload(file) {
    const meta = await uploadFile(file)
    setDataset(meta)
    setResponse(null)
  }

  async function handleAsk() {
    if (!dataset || !question.trim()) return
    setLoading(true)
    const res = await ask(dataset.dataset_id, question)
    setResponse(res)
    setLoading(false)
  }

  return (
    <div className="app">
      <header className="hero">
        <h1>AI Business Analyst</h1>
        <p>Ask your business data a question. Get an evidence-backed answer.</p>
      </header>

      <Upload onUpload={handleUpload} dataset={dataset} />

      {dataset && (
        <QuestionBox
          value={question}
          onChange={setQuestion}
          onSubmit={handleAsk}
          loading={loading}
        />
      )}

      {response && response.status === 'insufficient' && (
        <InsufficientEvidence failure={response.failure} trace={response.trace} />
      )}

      {response && response.status === 'ok' && (
        <>
          <AnswerCard
            answer={response.answer}
            explanation={response.explanation}
            recommendation={response.recommendation}
            confidence={response.confidence}
          />
          <ChartView chart={response.chart} />
          <EvidencePanel evidence={response.evidence} />
          <TraceTimeline trace={response.trace} />
          <ApprovalBar answerId={response.answer_id} approval={response.approval} />
        </>
      )}
    </div>
  )
}