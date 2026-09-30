import { useEffect, useState } from 'react'
import { apiUrl } from './api'
import MigrationWaves from './pages/MigrationWaves'
import './App.css'
import CostRisk from './pages/CostRisk'
import Copilot from './pages/Copilot'
import Applications from './pages/Applications'
import Recommendations from './pages/Recommendations'

const DASHBOARD_SAMPLE_SIZE = 12

function App() {
  const [activePage, setActivePage] = useState('dashboard')

  const [totalApplications, setTotalApplications] = useState(0)
  const [readyToMigrate, setReadyToMigrate] = useState(0)
  const [highRisk, setHighRisk] = useState(0)
  const [estimatedCost, setEstimatedCost] = useState(0)
  const [strategyCounts, setStrategyCounts] = useState({})
  const [migrationWaves, setMigrationWaves] = useState([])
  const [portfolio, setPortfolio] = useState([])
  const [dashboardStatus, setDashboardStatus] = useState('Connecting to backend')
  const [dashboardError, setDashboardError] = useState('')

  useEffect(() => {
    async function loadDashboardData() {
      try {
        // Get applications
        const applicationsResponse = await fetch(
          apiUrl('/applications')
        )

        if (!applicationsResponse.ok) {
          throw new Error('Failed to fetch applications')
        }

        const applications = await applicationsResponse.json()

        setTotalApplications(applications.length)
        const analyzedApplications = applications.slice(0, DASHBOARD_SAMPLE_SIZE)

        // Keep dashboard analysis bounded; the detailed pages are paginated.
        const recommendations = await Promise.all(
          analyzedApplications.map(async (app) => {
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
              throw new Error(
                `Failed to get recommendation for ${app.id}`
              )
            }

            return response.json()
          })
        )

        // Count applications ready to migrate
        const ready = recommendations.filter(
          (item) =>
            item.recommendation !== 'Retain' &&
            item.recommendation !== 'Retire'
        ).length

        setReadyToMigrate(ready)

        // Count applications by strategy
        const counts = {}

        recommendations.forEach((item) => {
          const strategy = item.recommendation

          counts[strategy] = (counts[strategy] || 0) + 1
        })

        setStrategyCounts(counts)

        // Get migration waves
        const wavesResponse = await fetch(
              apiUrl('/migration-waves'),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              application_ids: analyzedApplications.map((app) => app.id),
            }),
          }
        )

        if (!wavesResponse.ok) {
          throw new Error('Failed to fetch migration waves')
        }

        const wavesData = await wavesResponse.json()

        setMigrationWaves(wavesData.waves)

        // Get cost and risk for the dashboard sample
        const costRisks = await Promise.all(
          analyzedApplications.map(async (app) => {
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
              throw new Error(
                `Failed to get cost and risk for ${app.id}`
              )
            }

            return response.json()
          })
        )

        // Count high-risk applications
        const highRiskCount = costRisks.filter(
          (item) => item.risk_score >= 70
        ).length

        setHighRisk(highRiskCount)

        // Calculate total monthly AWS cost
        const totalCost = costRisks.reduce(
          (total, item) => total + item.monthly_aws_cost,
          0
        )

        setEstimatedCost(totalCost)

        // Create recommendation lookup
        const recommendationMap = {}

        recommendations.forEach((item) => {
          recommendationMap[item.application_id] =
            item.recommendation
        })

        // Create risk lookup
        const riskMap = {}

        costRisks.forEach((item) => {
          riskMap[item.application_id] = item.risk_score
        })

        // Create final portfolio data
        const portfolioData = analyzedApplications.map((app) => ({
          ...app,
          recommendation:
            recommendationMap[app.id] || 'N/A',
          riskScore: riskMap[app.id] ?? 0,
        }))

        setPortfolio(portfolioData)
        setDashboardStatus('Backend connected')
      } catch (error) {
        setDashboardStatus('Backend unavailable')
        setDashboardError(error.message || 'Failed to load dashboard data.')
      }
    }

    loadDashboardData()
  }, [])

  // Convert risk score to text
  const getRiskLabel = (score) => {
    if (score >= 70) return 'High'
    if (score >= 40) return 'Medium'
    return 'Low'
  }

  // Get CSS class for risk
  const getRiskClass = (score) => {
    if (score >= 70) return 'orange'
    if (score >= 40) return 'orange'
    return 'green'
  }

  // Get CSS class for recommendation
  const getRecommendationClass = (recommendation) => {
    if (recommendation === 'Refactor') {
      return 'purple'
    }

    if (recommendation === 'Rehost') {
      return 'blue'
    }

    if (recommendation === 'Replatform') {
      return 'blue'
    }

    if (recommendation === 'Repurchase') {
      return 'green'
    }

    if (recommendation === 'Retain') {
      return 'orange'
    }

    if (recommendation === 'Retire') {
      return 'orange'
    }

    return 'blue'
  }

  return (
    <div className="app">

      {/* Sidebar */}
      <aside className="sidebar">

        <div className="logo">
          ☁️

          <div>
            <h2>CloudPilot</h2>
            <span>Migration AI</span>
          </div>
        </div>

        <nav>

          <a
            className={
              activePage === 'dashboard'
                ? 'active'
                : ''
            }
            onClick={() => setActivePage('dashboard')}
          >
            🏠 Dashboard
          </a>

          <a
            className={
              activePage === 'applications'
                ? 'active'
                : ''
            }
            onClick={() => setActivePage('applications')}
          >
            📱 Applications
          </a>

          <a
            className={
              activePage === 'recommendations'
                ? 'active'
                : ''
            }
            onClick={() =>
              setActivePage('recommendations')
            }
          >
            🎯 Recommendations
          </a>

          <a
            className={
              activePage === 'waves'
                ? 'active'
                : ''
            }
            onClick={() => setActivePage('waves')}
          >
            🔄 Migration Waves
          </a>

          <a
            className={
              activePage === 'cost-risk'
                ? 'active'
                : ''
            }
            onClick={() =>
              setActivePage('cost-risk')
            }
          >
            💰 Cost & Risk
          </a>

          <a
            className={
              activePage === 'copilot'
                ? 'active'
                : ''
            }
            onClick={() => setActivePage('copilot')}
          >
            🤖 AI Copilot
          </a>

        </nav>

        <div className="sidebar-bottom">
          <p>Migration Planning</p>
          <small>AI-powered cloud insights</small>
        </div>

      </aside>

      {/* Main Content */}
      <main className="main">

        {activePage === 'applications' ? (
          <Applications />

        ) : activePage === 'recommendations' ? (
          <Recommendations />

        ) : activePage === 'waves' ? (
          <MigrationWaves />

        ) : activePage === 'cost-risk' ? (
          <CostRisk />

        ) : activePage === 'copilot' ? (
          <Copilot />

        ) : (

          <>
            {/* Header */}
            <header className="header">

              <div>
                <h1>Migration Dashboard</h1>

                <p>
                    Planning metrics for the first {DASHBOARD_SAMPLE_SIZE} applications
                </p>
              </div>

              <div className={`status ${dashboardError ? 'error' : dashboardStatus === 'Backend connected' ? 'connected' : 'connecting'}`}>
                <span></span>
                {dashboardStatus}
              </div>

            </header>
            {dashboardError && <p className="dashboard-error" role="alert">{dashboardError}</p>}

            {/* Metrics */}
            <section className="metrics">

              {/* Total Applications */}
              <div className="card metric-card">

                <div className="metric-icon">
                  📱
                </div>

                <div>
                  <p>Total Applications</p>

                  <h2>
                    {totalApplications}
                  </h2>

                  <small>
                    Applications discovered
                  </small>
                </div>

              </div>

              {/* Ready to Migrate */}
              <div className="card metric-card">

                <div className="metric-icon">
                  🎯
                </div>

                <div>
                  <p>Ready to Migrate</p>

                  <h2>
                    {readyToMigrate}
                  </h2>

                  <small>
                    Based on AI recommendations
                  </small>
                </div>

              </div>

              {/* High Risk */}
              <div className="card metric-card">

                <div className="metric-icon">
                  ⚠️
                </div>

                <div>
                  <p>High Risk</p>

                  <h2>
                    {highRisk}
                  </h2>

                  <small>
                    Need attention
                  </small>
                </div>

              </div>

              {/* Estimated Cost */}
              <div className="card metric-card">

                <div className="metric-icon">
                  💰
                </div>

                <div>
                  <p>Estimated Cost</p>

                  <h2>
                    ${estimatedCost.toLocaleString()}
                  </h2>

                  <small>
                    Monthly AWS estimate
                  </small>
                </div>

              </div>

            </section>

            {/* Dashboard Content */}
            <section className="dashboard-grid">

              {/* Migration Overview */}
              <div className="card large-card">

                <div className="card-header">

                  <div>
                    <h2>Migration Overview</h2>

                    <p>
                      Application migration strategy
                      distribution
                    </p>
                  </div>

                </div>

                <div className="strategy-list">

                  {/* Rehost */}
                  <div className="strategy">

                    <span>Rehost</span>

                    <div className="progress">
                      <div
                        style={{
                          width:
                            totalApplications > 0
                              ? `${((strategyCounts.Rehost || 0) / totalApplications) * 100}%`
                              : '0%',
                        }}
                      ></div>
                    </div>

                    <strong>
                      {strategyCounts.Rehost || 0}
                    </strong>

                  </div>

                  {/* Replatform */}
                  <div className="strategy">

                    <span>Replatform</span>

                    <div className="progress">
                      <div
                        style={{
                          width:
                            totalApplications > 0
                              ? `${((strategyCounts.Replatform || 0) / totalApplications) * 100}%`
                              : '0%',
                        }}
                      ></div>
                    </div>

                    <strong>
                      {strategyCounts.Replatform || 0}
                    </strong>

                  </div>

                  {/* Refactor */}
                  <div className="strategy">

                    <span>Refactor</span>

                    <div className="progress">
                      <div
                        style={{
                          width:
                            totalApplications > 0
                              ? `${((strategyCounts.Refactor || 0) / totalApplications) * 100}%`
                              : '0%',
                        }}
                      ></div>
                    </div>

                    <strong>
                      {strategyCounts.Refactor || 0}
                    </strong>

                  </div>

                  {/* Retain */}
                  <div className="strategy">

                    <span>Retain</span>

                    <div className="progress">
                      <div
                        style={{
                          width:
                            totalApplications > 0
                              ? `${((strategyCounts.Retain || 0) / totalApplications) * 100}%`
                              : '0%',
                        }}
                      ></div>
                    </div>

                    <strong>
                      {strategyCounts.Retain || 0}
                    </strong>

                  </div>

                  {/* Retire */}
                  <div className="strategy">

                    <span>Retire</span>

                    <div className="progress">
                      <div
                        style={{
                          width:
                            totalApplications > 0
                              ? `${((strategyCounts.Retire || 0) / totalApplications) * 100}%`
                              : '0%',
                        }}
                      ></div>
                    </div>

                    <strong>
                      {strategyCounts.Retire || 0}
                    </strong>

                  </div>

                  {/* Repurchase */}
                  <div className="strategy">

                    <span>Repurchase</span>

                    <div className="progress">
                      <div
                        style={{
                          width:
                            totalApplications > 0
                              ? `${((strategyCounts.Repurchase || 0) / totalApplications) * 100}%`
                              : '0%',
                        }}
                      ></div>
                    </div>

                    <strong>
                      {strategyCounts.Repurchase || 0}
                    </strong>

                  </div>

                </div>

              </div>

              {/* Migration Waves */}
              <div className="card">

                <div className="card-header">

                  <div>
                    <h2>Migration Waves</h2>

                    <p>
                      Current migration plan
                    </p>
                  </div>

                </div>

                {migrationWaves.map((wave) => (
                  <div
                    className="wave"
                    key={wave.wave}
                  >

                    <div>
                      <strong>
                        Wave {wave.wave}
                      </strong>

                      <span>
                        {wave.risk} Risk
                      </span>
                    </div>

                    <b>
                      {wave.applications.length} Apps
                    </b>

                  </div>
                ))}

              </div>

            </section>

            {/* Application Portfolio */}
            <section className="card applications">

              <div className="card-header">

                <div>
                  <h2>Application Portfolio</h2>

                  <p>
                    Analyzed sample ({portfolio.length} of {totalApplications})
                  </p>
                </div>

                <button
                  onClick={() =>
                    setActivePage('applications')
                  }
                >
                  View All
                </button>

              </div>

              <table>

                <thead>

                  <tr>
                    <th>Application</th>
                    <th>Technology</th>
                    <th>Criticality</th>
                    <th>Recommendation</th>
                    <th>Risk</th>
                  </tr>

                </thead>

                <tbody>

                  {portfolio.map((app) => {

                    const riskLabel =
                      getRiskLabel(app.riskScore)

                    const riskClass =
                      getRiskClass(app.riskScore)

                    const recommendationClass =
                      getRecommendationClass(
                        app.recommendation
                      )

                    return (
                      <tr key={app.id}>

                        <td>
                          {app.name}
                        </td>

                        <td>
                          {app.technology}
                        </td>

                        <td>
                          {app.criticality}
                        </td>

                        <td>
                          <span
                            className={`badge ${recommendationClass}`}
                          >
                            {app.recommendation}
                          </span>
                        </td>

                        <td>
                          <span
                            className={`badge ${riskClass}`}
                          >
                            {riskLabel}
                          </span>
                        </td>

                      </tr>
                    )
                  })}

                </tbody>

              </table>

            </section>

          </>

        )}

      </main>

    </div>
  )
}

export default App