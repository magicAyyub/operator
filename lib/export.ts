"use server"

import { mockSecurityData, mockDetailedInData } from "./mock-data"

export async function exportToCSV(queryString) {
  console.log("Simulation d'exportation CSV avec paramètres:", queryString)

  // Simuler un délai pour imiter une vraie exportation
  await new Promise((resolve) => setTimeout(resolve, 1000))

  // Simuler la génération d'un fichier CSV
  const params = new URLSearchParams(queryString)

  // Filtrer les données simulées en fonction des filtres
  let filteredData = [...mockSecurityData]

  if (params.get("statut") && params.get("statut") !== "all") {
    filteredData = filteredData.filter((item) => item.statut === params.get("statut"))
  }

  if (params.get("fa_statut") && params.get("fa_statut") !== "all") {
    filteredData = filteredData.filter((item) => item.fa_statut === params.get("fa_statut"))
  }

  if (params.get("limite_type") && params.get("limite_valeur") && params.get("limite_type") !== "none") {
    const value = Number.parseFloat(params.get("limite_valeur"))
    if (params.get("limite_type") === "lt") {
      filteredData = filteredData.filter((item) => item.pourcentage_in < value)
    } else {
      filteredData = filteredData.filter((item) => item.pourcentage_in > value)
    }
  }

  // Générer le contenu CSV
  const headers = ["Opérateur", "Nombre d'IN", "% IN (parc global)", "Statut", "2FA_Statut", "Date"]
  const rows = filteredData.map((row) => [
    row.operateur,
    row.nombre_in,
    row.pourcentage_in,
    row.statut,
    row.fa_statut,
    new Date(row.date).toISOString().split("T")[0],
  ])

  const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n")

  // Simuler le retour d'un fichier
  return {
    content: csvContent,
    fileName: `export_securite_${new Date().toISOString().split("T")[0]}.csv`,
  }

  /* 
  POUR L'IMPLÉMENTATION RÉELLE:
  
  const params = new URLSearchParams(queryString)

  let queryText = `
    SELECT 
      d.operateur,
      d.nombre_in,
      d.pourcentage_in,
      d.statut,
      d.fa_statut,
      d.date
    FROM security_data d
    WHERE 1=1
  `

  const queryParams = []
  let paramIndex = 1

  if (params.get("statut") && params.get("statut") !== 'all') {
    queryText += ` AND d.statut = $${paramIndex}`
    queryParams.push(params.get("statut"))
    paramIndex++
  }

  if (params.get("fa_statut") && params.get("fa_statut") !== 'all') {
    queryText += ` AND d.fa_statut = $${paramIndex}`
    queryParams.push(params.get("fa_statut"))
    paramIndex++
  }

  if (params.get("limite_type") && params.get("limite_valeur") && params.get("limite_type") !== 'none') {
    const operator = params.get("limite_type") === "lt" ? "<" : ">"
    queryText += ` AND d.pourcentage_in ${operator} $${paramIndex}`
    queryParams.push(Number.parseFloat(params.get("limite_valeur")))
    paramIndex++
  }

  if (params.get("date_min")) {
    queryText += ` AND d.date >= $${paramIndex}`
    queryParams.push(params.get("date_min"))
    paramIndex++
  }

  if (params.get("date_max")) {
    queryText += ` AND d.date <= $${paramIndex}`
    queryParams.push(params.get("date_max"))
    paramIndex++
  }

  if (params.get("annee") && params.get("annee") !== 'all') {
    queryText += ` AND EXTRACT(YEAR FROM d.date) = $${paramIndex}`
    queryParams.push(Number.parseInt(params.get("annee")))
    paramIndex++
  }

  queryText += ` ORDER BY d.date DESC`

  const result = await query(queryText, queryParams)

  // Convert to CSV
  const headers = ["Opérateur", "Nombre d'IN", "% IN (parc global)", "Statut", "2FA_Statut", "Date"]
  const rows = result.rows.map((row) => [
    row.operateur,
    row.nombre_in,
    row.pourcentage_in,
    row.statut,
    row.fa_statut,
    new Date(row.date).toISOString().split("T")[0],
  ])

  const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n")
  
  return {
    content: csvContent,
    fileName: `export_securite_${new Date().toISOString().split("T")[0]}.csv`
  }
  */
}

export async function exportDetailedInData(queryString) {
  console.log("Simulation d'exportation des données détaillées des IN avec paramètres:", queryString)

  // Simuler un délai pour imiter une vraie exportation
  await new Promise((resolve) => setTimeout(resolve, 1200))

  // Simuler la génération d'un fichier CSV
  const params = new URLSearchParams(queryString)

  // Filtrer les données simulées en fonction des filtres
  let filteredData = [...mockSecurityData]

  if (params.get("statut") && params.get("statut") !== "all") {
    filteredData = filteredData.filter((item) => item.statut === params.get("statut"))
  }

  if (params.get("fa_statut") && params.get("fa_statut") !== "all") {
    filteredData = filteredData.filter((item) => item.fa_statut === params.get("fa_statut"))
  }

  // Récupérer les ID_LIN des opérateurs filtrés
  const filteredLinIds = filteredData.map((item) => item.id_lin)

  // Filtrer les données détaillées des IN en fonction des ID_LIN
  const filteredInData = mockDetailedInData.filter((item) => filteredLinIds.includes(item.id_lin))

  // Générer le contenu CSV
  const headers = ["ID_LIN", "Numéro IN", "Date d'activation", "Statut détaillé", "Type de service", "Région"]
  const rows = filteredInData.map((row) => [
    row.id_lin,
    row.numero_in,
    new Date(row.date_activation).toISOString().split("T")[0],
    row.statut_detail,
    row.type_service,
    row.region,
  ])

  const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n")

  // Simuler le retour d'un fichier
  return {
    content: csvContent,
    fileName: `export_in_details_${new Date().toISOString().split("T")[0]}.csv`,
  }

  /* 
  POUR L'IMPLÉMENTATION RÉELLE:
  
  const params = new URLSearchParams(queryString)

  // D'abord, récupérer les ID_LIN des opérateurs filtrés
  let operatorQueryText = `
    SELECT DISTINCT id_lin
    FROM security_data d
    WHERE 1=1
  `

  const queryParams = []
  let paramIndex = 1

  if (params.get("statut") && params.get("statut") !== 'all') {
    operatorQueryText += ` AND d.statut = $${paramIndex}`
    queryParams.push(params.get("statut"))
    paramIndex++
  }

  if (params.get("fa_statut") && params.get("fa_statut") !== 'all') {
    operatorQueryText += ` AND d.fa_statut = $${paramIndex}`
    queryParams.push(params.get("fa_statut"))
    paramIndex++
  }

  if (params.get("limite_type") && params.get("limite_valeur") && params.get("limite_type") !== 'none') {
    const operator = params.get("limite_type") === "lt" ? "<" : ">"
    operatorQueryText += ` AND d.pourcentage_in ${operator} $${paramIndex}`
    queryParams.push(Number.parseFloat(params.get("limite_valeur")))
    paramIndex++
  }

  if (params.get("date_min")) {
    operatorQueryText += ` AND d.date >= $${paramIndex}`
    queryParams.push(params.get("date_min"))
    paramIndex++
  }

  if (params.get("date_max")) {
    operatorQueryText += ` AND d.date <= $${paramIndex}`
    queryParams.push(params.get("date_max"))
    paramIndex++
  }

  if (params.get("annee") && params.get("annee") !== 'all') {
    operatorQueryText += ` AND EXTRACT(YEAR FROM d.date) = $${paramIndex}`
    queryParams.push(Number.parseInt(params.get("annee")))
    paramIndex++
  }

  const operatorResult = await query(operatorQueryText, queryParams)
  const linIds = operatorResult.rows.map(row => row.id_lin)
  
  if (linIds.length === 0) {
    return {
      content: "ID_LIN,Numéro IN,Date d'activation,Statut détaillé,Type de service,Région",
      fileName: `export_in_details_${new Date().toISOString().split("T")[0]}.csv`
    }
  }

  // Ensuite, récupérer les données détaillées des IN pour ces ID_LIN
  const inQueryText = `
    SELECT 
      id_lin,
      numero_in,
      date_activation,
      statut_detail,
      type_service,
      region
    FROM in_details
    WHERE id_lin = ANY($1)
    ORDER BY id_lin, numero_in
  `

  const inResult = await query(inQueryText, [linIds])

  // Convert to CSV
  const headers = ["ID_LIN", "Numéro IN", "Date d'activation", "Statut détaillé", "Type de service", "Région"]
  const rows = inResult.rows.map((row) => [
    row.id_lin,
    row.numero_in,
    new Date(row.date_activation).toISOString().split("T")[0],
    row.statut_detail,
    row.type_service,
    row.region
  ])

  const csvContent = [headers.join(","), ...rows.map((row) => row.join(","))].join("\n")
  
  return {
    content: csvContent,
    fileName: `export_in_details_${new Date().toISOString().split("T")[0]}.csv`
  }
  */
}

