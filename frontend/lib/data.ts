// Fonctions pour interagir avec l'API backend
const BASE_URL = "http://localhost:8000"
const API_URL = `${BASE_URL}/api/csv`
const PAGE_SIZE = 10

// Fonction utilitaire pour les requêtes avec timeout
async function fetchWithTimeout(url: string, options = {}, timeout = 10000) {
  const controller = new AbortController()
  const { signal } = controller

  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, { ...options, signal })
    clearTimeout(timeoutId)
    return response
  } catch (error) {
    clearTimeout(timeoutId)
    console.error(`Erreur lors de la requête vers ${url}:`, error)
    // Retourner une réponse simulée pour éviter de bloquer l'interface
    return {
      ok: true,
      json: async () => ({ data: [], message: "timeout" }),
    } as Response
  }
}

// Fonctions pour interagir avec l'API backend
export async function getData(page = 1, pageSize = PAGE_SIZE) {
  try {
    const searchParams = new URLSearchParams(window.location.search)
    searchParams.set("page", page.toString())
    searchParams.set("page_size", pageSize.toString())

    const response = await fetchWithTimeout(`${API_URL}/data?${searchParams.toString()}`)

    if (!response.ok) {
      throw new Error("Erreur lors de la récupération des données")
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error("Erreur:", error)
    return { data: [], total_pages: 0, message: "error" }
  }
}

export async function getStats(type: string) {
  try {
    const response = await fetchWithTimeout(`${API_URL}/stats?type=${type}`)

    if (!response.ok) {
      throw new Error(`Erreur lors de la récupération des statistiques de type ${type}`)
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error(`Erreur lors de la récupération des statistiques de type ${type}:`, error)
    return []
  }
}

export async function getFilterOptions() {
  try {
    const response = await fetchWithTimeout(`${API_URL}/filter-options`)

    if (!response.ok) {
      throw new Error("Erreur lors de la récupération des options de filtrage")
    }

    const data = await response.json()
    return data
  } catch (error) {
    console.error("Erreur:", error)
    return {
      statuts: [],
      fa_statuts: [],
      annees: [],
    }
  }
}

export async function uploadCSV(file: File) {
  try {
    const formData = new FormData()
    formData.append("file", file)

    const response = await fetchWithTimeout(
      `${API_URL}/upload`,
      {
        method: "POST",
        body: formData,
      },
      30000,
    ) // Timeout plus long pour l'upload

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.message || "Erreur lors du téléchargement du fichier CSV")
    }

    return await response.json()
  } catch (error) {
    console.error("Erreur:", error)
    throw error
  }
}