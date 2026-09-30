import { useEffect, useState } from 'react'
import { apiUrl } from '../api'

function MigrationWaves() {
  const [applications, setApplications] = useState([])
  const [waves, setWaves] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    async function loadMigrationWaves() {
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

        // Get migration waves
        const wavesResponse = await fetch(
          apiUrl('/migration-waves'),
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              application_ids: apps.map((app) => app.id),
            }),
          }
        )

        if (!wavesResponse.ok) {
          throw new Error('Failed to fetch migration waves')
        }

        const data = await wavesResponse.json()
        setWaves(data.waves)
        setLoading(false)
      } catch (err) {
        console.error(err)
        setError('Unable to load migration waves from backend')
        setLoading(false)
      }
    }

    loadMigrationWaves()
  }, [])

  const getApplicationName = (id) => {
    const application = applications.find((app) => app.id === id)
    return application ? application.name : id
  }

  if (loading) {
    return (
      <div className="page">
        <h1>Migration Waves</h1>
        <p>Loading migration waves...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <h1>Migration Waves</h1>
        <p>{error}</p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Migration Waves</h1>
          <p>
            AI-planned migration sequence based on application dependencies
            and risk.
          </p>
        </div>

        <div className="application-count">
          {waves.length} Waves
        </div>
      </div>

      <div className="wave-grid">
        {waves.map((wave) => (
          <div className="card migration-wave-card" key={wave.wave}>
            <div className="wave-card-header">
              <div>
                <span className="wave-label">WAVE</span>
                <h2>Wave {wave.wave}</h2>
              </div>

              <span
                className={`wave-risk ${wave.risk.toLowerCase()}`}
              >
                {wave.risk} Risk
              </span>
            </div>

            <div className="wave-applications">
              <h3>Applications</h3>

              {wave.applications.map((applicationId) => (
                <div
                  className="wave-application"
                  key={applicationId}
                >
                  <div>
                    <strong>
                      {getApplicationName(applicationId)}
                    </strong>
                    <span>{applicationId}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default MigrationWaves