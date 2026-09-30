import { useEffect, useState } from 'react'
import { apiUrl } from '../api'

const PAGE_SIZE = 20

function Recommendations() {
  const [applications, setApplications] = useState([])
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [currentPage, setCurrentPage] = useState(0)

  useEffect(() => {
    async function loadRecommendations() {
      try {
        // Get applications from backend
        const applicationsResponse = await fetch(
          apiUrl('/applications')
        )

        if (!applicationsResponse.ok) {
          throw new Error('Failed to fetch applications')
        }

        const apps = await applicationsResponse.json()
        setApplications(apps)

        // Get recommendation for each application
        const recommendationResults = await Promise.all(
          apps.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE).map(async (app) => {
            const response = await fetch(
              apiUrl('/recommendation'),
              {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  application_id: app.id,
                }),
              }
            )

            if (!response.ok) {
              const detail = await response.json().catch(() => ({}))
              throw new Error(detail.detail || `Failed for ${app.id}`)
            }

            return response.json()
          })
        )

        setRecommendations(recommendationResults)
        setLoading(false)
      } catch (err) {
        console.error(err)
        setError(err.message || 'Unable to load recommendations from backend')
        setLoading(false)
      }
    }

    loadRecommendations()
  }, [currentPage])

  if (loading) {
    return (
      <div className="page">
        <h1>6R Recommendations</h1>
        <p>Loading recommendations...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <h1>6R Recommendations</h1>
        <p>{error}</p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>6R Recommendations</h1>
          <p>
            AI-powered migration strategy recommendations for applications.
          </p>
        </div>

        <div className="application-count">
          Showing {currentPage * PAGE_SIZE + 1}-{Math.min((currentPage + 1) * PAGE_SIZE, applications.length)} of {applications.length}
        </div>
      </div>

      <div className="recommendation-grid">
        {recommendations.map((recommendation) => {
          const application = applications.find(
            (app) => app.id === recommendation.application_id
          )
          const explanation = recommendation.explanation
          const explanationText = typeof explanation === 'string'
            ? explanation
            : explanation?.shap?.summary || explanation?.summary || 'No explanation was returned.'
          const contributors = typeof explanation === 'object'
            ? explanation?.shap?.top_contributors || explanation?.top_contributors || []
            : []
          const probabilities = typeof explanation === 'object'
            ? explanation?.probabilities || {}
            : {}

          return (
            <div
              className="card recommendation-card"
              key={recommendation.application_id}
            >
              <div className="recommendation-top">
                <div>
                  <h2>{application?.name}</h2>
                  <span>{recommendation.application_id}</span>
                </div>

                <span className="strategy-badge">
                  {recommendation.recommendation}
                </span>
              </div>

              <div className="confidence">
                <div className="confidence-header">
                  <span>AI Confidence</span>

                  <strong>
                    {Math.round(recommendation.confidence * 100)}%
                  </strong>
                </div>

                <div className="confidence-bar">
                  <div
                    style={{
                      width: `${recommendation.confidence * 100}%`,
                    }}
                  ></div>
                </div>
              </div>

              <div className="explanation">
                <strong>Why this recommendation?</strong>
                <p>{explanationText}</p>
                {contributors.length > 0 && (
                  <ul>
                    {contributors.map((item) => (
                      <li key={item.feature}>
                        {item.feature}: {item.value} (SHAP {item.impact})
                      </li>
                    ))}
                  </ul>
                )}
                {Object.keys(probabilities).length > 0 && (
                  <p>Class probabilities: {Object.entries(probabilities)
                    .map(([strategy, probability]) => `${strategy} ${Math.round(probability * 100)}%`)
                    .join(' | ')}</p>
                )}
              </div>
            </div>
          )
        })}
      </div>
      <div className="pagination-controls">
        <button disabled={currentPage === 0} onClick={() => setCurrentPage((page) => page - 1)}>
          Previous
        </button>
        <span>Page {currentPage + 1} of {Math.max(1, Math.ceil(applications.length / PAGE_SIZE))}</span>
        <button
          disabled={(currentPage + 1) * PAGE_SIZE >= applications.length}
          onClick={() => setCurrentPage((page) => page + 1)}
        >
          Next
        </button>
      </div>
    </div>
  )
}

export default Recommendations