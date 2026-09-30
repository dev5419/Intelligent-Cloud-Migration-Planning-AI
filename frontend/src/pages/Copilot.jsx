import { useState } from 'react'
import { apiUrl } from '../api'

function Copilot() {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const askCopilot = async () => {
    if (!question.trim()) {
      return
    }

    setLoading(true)
    setError('')
    setAnswer(null)

    try {
      const response = await fetch(
        apiUrl('/copilot'),
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            question: question,
          }),
        }
      )

      if (!response.ok) {
        const detail = await response.json().catch(() => ({}))
        throw new Error(detail.detail || `Request failed (${response.status})`)
      }

      const data = await response.json()
      setAnswer(data)
    } catch (err) {
      console.error(err)
      setError(err.message || 'Unable to connect to AI Copilot')
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      askCopilot()
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>AI Copilot</h1>
          <p>
            Ask questions about your cloud migration plan.
          </p>
        </div>

        <div className="application-count">
          AI Assistant
        </div>
      </div>

      <div className="card copilot-card">

        <div className="copilot-intro">
          <div className="copilot-icon">🤖</div>

          <div>
            <h2>Migration Copilot</h2>
            <p>
              Get AI-powered guidance for your migration strategy.
            </p>
          </div>
        </div>

        <div className="question-box">
          <textarea
            placeholder="Ask something like: Which applications should we migrate first?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            rows="4"
          />

          <button
            onClick={askCopilot}
            disabled={loading || !question.trim()}
          >
            {loading ? 'Thinking...' : 'Ask Copilot'}
          </button>
        </div>

        {error && (
          <div className="copilot-error" role="alert">
            {error}
          </div>
        )}

        {answer && (
          <div className="copilot-answer">

            <div className="answer-header">
              <h3>🤖 Copilot Response</h3>
            </div>

            <p className="answer-text">
              {answer.answer}
            </p>

            <div className="sources">
              <strong>Sources</strong>

              <div className="source-list">
                {answer.sources.map((source, index) => (
                  <span key={index}>
                    {source}
                  </span>
                ))}
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  )
}

export default Copilot