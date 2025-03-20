"use server"

import { cache } from "react"
import { mockSecurityData, mockFilterOptions, mockStats } from "./mock-data"

export async function getData(page = 1, filters = {}) {
  console.log("Simulation de récupération de données avec filtres:", filters)

  // Simuler un délai pour imiter une vraie requête
  await new Promise((resolve) => setTimeout(resolve, 500))

  // Filtrer les données simulées en fonction des filtres
  let filteredData = [...mockSecurityData]

  if (filters.statut && filters.statut !== "all") {
    filteredData = filteredData.filter((item) => item.statut === filters.statut)
  }

  if (filters.fa_statut && filters.fa_statut !== "all") {
    filteredData = filteredData.filter((item) => item.fa_statut === filters.fa_statut)
  }

  if (filters.limite_type && filters.limite_valeur && filters.limite_type !== "none") {
    const value = Number.parseFloat(filters.limite_valeur)
    if (filters.limite_type === "lt") {
      filteredData = filteredData.filter((item) => item.pourcentage_in < value)
    } else {
      filteredData = filteredData.filter((item) => item.pourcentage_in > value)
    }
  }

  if (filters.date_min) {
    const minDate = new Date(filters.date_min)
    filteredData = filteredData.filter((item) => new Date(item.date) >= minDate)
  }

  if (filters.date_max) {
    const maxDate = new Date(filters.date_max)
    filteredData = filteredData.filter((item) => new Date(item.date) <= maxDate)
  }

  if (filters.annee && filters.annee !== "all") {
    const year = Number.parseInt(filters.annee)
    filteredData = filteredData.filter((item) => new Date(item.date).getFullYear() === year)
  }

  // Trier par date décroissante
  filteredData.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())

  // Pagination
  const pageSize = 10
  const offset = (page - 1) * pageSize
  const paginatedData = filteredData.slice(offset, offset + pageSize)

  return {
    data: paginatedData,
    total: filteredData.length,
    totalPages: Math.ceil(filteredData.length / pageSize),
  }

  /* 
  POUR L'IMPLÉMENTATION RÉELLE:
  
  const pageSize = 10
  const offset = (page - 1) * pageSize

  let queryText = `
    SELECT 
      d.id,
      d.operateur,
      d.nombre_in,
      d.pourcentage_in,
      d.statut,
      d.fa_statut,
      d.date
    FROM security_data d
    WHERE 1=1
  `

  const params = []
  let paramIndex = 1

  if (filters.statut && filters.statut !== 'all') {
    queryText += ` AND d.statut = $${paramIndex}`
    params.push(filters.statut)
    paramIndex++
  }

  if (filters.fa_statut && filters.fa_statut !== 'all') {
    queryText += ` AND d.fa_statut = $${paramIndex}`
    params.push(filters.fa_statut)
    paramIndex++
  }

  if (filters.limite_type && filters.limite_valeur && filters.limite_type !== 'none') {
    const operator = filters.limite_type === "lt" ? "<" : ">"
    queryText += ` AND d.pourcentage_in ${operator} $${paramIndex}`
    params.push(Number.parseFloat(filters.limite_valeur))
    paramIndex++
  }

  if (filters.date_min) {
    queryText += ` AND d.date >= $${paramIndex}`
    params.push(filters.date_min)
    paramIndex++
  }

  if (filters.date_max) {
    queryText += ` AND d.date <= $${paramIndex}`
    params.push(filters.date_max)
    paramIndex++
  }

  if (filters.annee && filters.annee !== 'all') {
    queryText += ` AND EXTRACT(YEAR FROM d.date) = $${paramIndex}`
    params.push(Number.parseInt(filters.annee))
    paramIndex++
  }

  // Count total rows for pagination
  const countQuery =
    `
    SELECT COUNT(*) as total
    FROM security_data d
    WHERE 1=1
  ` + queryText.split("WHERE 1=1")[1]

  const countResult = await query(countQuery, params)
  const total = Number.parseInt(countResult.rows[0].total)

  // Add pagination to the main query
  queryText += ` ORDER BY d.date DESC LIMIT ${pageSize} OFFSET ${offset}`

  const result = await query(queryText, params)

  return {
    data: result.rows,
    total,
    totalPages: Math.ceil(total / pageSize),
  }
  */
}

export const getFilterOptions = cache(async () => {
  console.log("Simulation de récupération des options de filtres")

  // Simuler un délai pour imiter une vraie requête
  await new Promise((resolve) => setTimeout(resolve, 300))

  // Retourner les options simulées
  return mockFilterOptions

  /* 
  POUR L'IMPLÉMENTATION RÉELLE:
  
  const statusResult = await query(`
    SELECT DISTINCT statut FROM security_data ORDER BY statut
  `)

  const faStatusResult = await query(`
    SELECT DISTINCT fa_statut FROM security_data ORDER BY fa_statut
  `)

  const yearsResult = await query(`
    SELECT DISTINCT EXTRACT(YEAR FROM date)::int as year 
    FROM security_data 
    ORDER BY year DESC
  `)

  return {
    statuts: statusResult.rows.map((row) => row.statut),
    fa_statuts: faStatusResult.rows.map((row) => row.fa_statut),
    annees: yearsResult.rows.map((row) => row.year.toString()),
  }
  */
})

export const getStats = cache(async (type) => {
  console.log("Simulation de récupération des statistiques pour:", type)

  // Simuler un délai pour imiter une vraie requête
  await new Promise((resolve) => setTimeout(resolve, 400))

  // Retourner les statistiques simulées
  return mockStats[type] || []

  /* 
  POUR L'IMPLÉMENTATION RÉELLE:
  
  let queryText = ""

  switch (type) {
    case "operators":
      queryText = `
        SELECT 
          operateur as name, 
          ROUND(SUM(pourcentage_in)::numeric, 2) as value
        FROM security_data
        GROUP BY operateur
        ORDER BY value DESC
        LIMIT 5
      `
      break
    case "status":
      queryText = `
        SELECT 
          statut as name, 
          ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM security_data) * 100, 2) as value
        FROM security_data
        GROUP BY statut
        ORDER BY value DESC
      `
      break
    case "2fa":
      queryText = `
        SELECT 
          fa_statut as name, 
          ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM security_data) * 100, 2) as value
        FROM security_data
        GROUP BY fa_statut
        ORDER BY value DESC
      `
      break
    default:
      return []
  }

  const result = await query(queryText)
  return result.rows
  */
})

