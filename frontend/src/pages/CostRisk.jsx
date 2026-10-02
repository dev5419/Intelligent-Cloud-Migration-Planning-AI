import { useEffect, useState } from 'react'
import {
  apiUrl,
  mapWithConcurrency,
  COST_RISK_REQUEST_CONCURRENCY,
} from '../api'

const PAGE_SIZE = 20

function CostRisk() {
  const [applications, setApplications] = useState([])
  const [costRisks, setCostRisks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [currentPage, setCurrentPage] = useState(0)

  useEffect(() => {
    async function loadCostRisk() {
      try {
        // Get applications
        const applicationsResponse = await fetch(
          apiUrl('/applications')
        )

        if (!applicationsResponse.ok) {
          throw new Error('Failed to fetch applications')
        }

        const apps = await applicationsResponse.json()
        setApplications(apps)

        // Get cost and risk for each application
        const results = await mapWithConcurrency(
          apps.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE),
          COST_RISK_REQUEST_CONCURRENCY,
          async (app) => {
            const response = await fetch(
              apiUrl('/cost-risk'),
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
          }
        )

        setCostRisks(results)
        setLoading(false)
      } catch (err) {
        console.error(err)
        setError(err.message || 'Unable to load cost and risk data from backend')
        setLoading(false)
      }
    }

    loadCostRisk()
  }, [currentPage])

  const getApplicationName = (id) => {
    const application = applications.find(
      (app) => app.id === id
    )

    return application ? application.name : id
  }

  const getRiskClass = (score) => {
    if (score >= 70) return 'high'
    if (score >= 40) return 'medium'
    return 'low'
  }

  if (loading) {
    return (
      <div className="page">
        <h1>Cost & Risk</h1>
        <p>Loading cost and risk data...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <h1>Cost & Risk</h1>
        <p>{error}</p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Cost & Risk</h1>
          <p>
            Estimated cloud migration cost and application risk analysis.
          </p>
        </div>

        <div className="application-count">
          Showing {currentPage * PAGE_SIZE + 1}-{Math.min((currentPage + 1) * PAGE_SIZE, applications.length)} of {applications.length}
        </div>
      </div>

      <div className="cost-risk-grid">
        {costRisks.map((item) => (
          <div
            className="card cost-risk-card"
            key={item.application_id}
          >
            <div className="cost-risk-header">
              <div>
                <h2>{getApplicationName(item.application_id)}</h2>
                <span>{item.application_id}</span>
              </div>

              <span
                className={`risk-score ${getRiskClass(
                  item.risk_score
                )}`}
              >
                Risk {item.risk_score}
              </span>
            </div>

            <div className="cost-section">
              <p>Monthly AWS Cost</p>

              <h3>
                ${item.monthly_aws_cost.toLocaleString()}
              </h3>
            </div>

            <div className="cost-range">
              <div>
                <span>Lower Estimate</span>
                <strong>
                  ${item.cost_range.lower.toLocaleString()}
                </strong>
              </div>

              <div>
                <span>Upper Estimate</span>
                <strong>
                  ${item.cost_range.upper.toLocaleString()}
                </strong>
              </div>
            </div>

            <div className="risk-bar-section">
              <div className="risk-bar-header">
                <span>Risk Score</span>
                <strong>{item.risk_score}/100</strong>
              </div>

              <div className="risk-bar">
                <div
                  className={getRiskClass(item.risk_score)}
                  style={{
                    width: `${item.risk_score}%`,
                  }}
                ></div>
              </div>
            </div>
          </div>
        ))}
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

export default CostRisk