import { useEffect, useState } from 'react'
import { apiUrl } from '../api'

function Applications() {
  const [applications, setApplications] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(apiUrl('/applications'))
      .then((response) => {
        if (!response.ok) {
          throw new Error('Failed to fetch applications')
        }
        return response.json()
      })
      .then((data) => {
        setApplications(data)
        setLoading(false)
      })
      .catch((error) => {
        console.error(error)
        setError('Unable to connect to backend')
        setLoading(false)
      })
  }, [])

  const filteredApplications = applications.filter((app) =>
    app.name.toLowerCase().includes(search.toLowerCase()) ||
    app.id.toLowerCase().includes(search.toLowerCase()) ||
    app.technology.toLowerCase().includes(search.toLowerCase())
  )

  if (loading) {
    return (
      <div className="page">
        <h1>Application Portfolio</h1>
        <p>Loading applications...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="page">
        <h1>Application Portfolio</h1>
        <p>{error}</p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Application Portfolio</h1>
          <p>View and analyze all applications in the migration portfolio.</p>
        </div>

        <div className="application-count">
          {applications.length} Applications
        </div>
      </div>

      <div className="card application-table-card">
        <div className="table-top">
          <div>
            <h2>Applications</h2>
            <p>Application discovery and migration readiness</p>
          </div>

          <input
            type="text"
            placeholder="Search applications..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="table-container">
          <table className="application-table">
            <thead>
              <tr>
                <th>Application</th>
                <th>Owner</th>
                <th>Technology</th>
                <th>Criticality</th>
                <th>Dependencies</th>
              </tr>
            </thead>

            <tbody>
              {filteredApplications.map((app) => (
                <tr key={app.id}>
                  <td>
                    <div className="application-name">
                      <strong>{app.name}</strong>
                      <span>{app.id}</span>
                    </div>
                  </td>

                  <td>{app.owner}</td>

                  <td>{app.technology}</td>

                  <td>
                    <span
                      className={`criticality ${app.criticality.toLowerCase()}`}
                    >
                      {app.criticality}
                    </span>
                  </td>

                  <td>{app.dependencies.length}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {filteredApplications.length === 0 && (
            <p className="no-results">
              No applications found.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default Applications