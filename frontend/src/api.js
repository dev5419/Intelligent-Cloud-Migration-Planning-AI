export const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')

export const apiUrl = (path) => `${API_BASE_URL}${path}`

export const RECOMMENDATION_REQUEST_CONCURRENCY = 3
export const COST_RISK_REQUEST_CONCURRENCY = 3

export async function mapWithConcurrency(items, concurrency, mapper) {
  const results = new Array(items.length)
  const workerCount = Math.min(items.length, Math.max(1, Math.floor(concurrency)))
  let nextIndex = 0

  const workers = Array.from({ length: workerCount }, async () => {
    while (nextIndex < items.length) {
      const itemIndex = nextIndex
      nextIndex += 1
      results[itemIndex] = await mapper(items[itemIndex], itemIndex)
    }
  })

  await Promise.all(workers)
  return results
}
