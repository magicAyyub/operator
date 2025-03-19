"use client"

import { useState } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { useSearchParams } from "next/navigation"
import { useData } from "@/hooks/use-data"
import { Download, ChevronLeft, ChevronRight, FileSpreadsheet, AlertCircle, Database, FilterX } from "lucide-react"

export function DataTable() {
  const [page, setPage] = useState(1)
  const searchParams = useSearchParams()
  const { data, isLoading, totalPages } = useData(page)

  const handleExport = async () => {
    const params = new URLSearchParams(searchParams)
    params.set("export", "true")

    try {
      // Pour la démonstration, ouvrir une nouvelle fenêtre avec l'URL d'exportation
      // Dans un environnement réel, cela téléchargera le fichier CSV
      const exportUrl = `/api/export?${params.toString()}`
      window.open(exportUrl, "_blank")

      console.log("Simulation: Exportation démarrée avec les paramètres:", params.toString())
    } catch (error) {
      console.error("Erreur lors de l'exportation:", error)
    }
  }

  const handleExportInDetails = async () => {
    const params = new URLSearchParams(searchParams)
    params.set("export_details", "true")

    try {
      // Pour la démonstration, ouvrir une nouvelle fenêtre avec l'URL d'exportation
      // Dans un environnement réel, cela téléchargera le fichier CSV
      const exportUrl = `/api/export-in-details?${params.toString()}`
      window.open(exportUrl, "_blank")

      console.log("Simulation: Exportation des détails IN démarrée avec les paramètres:", params.toString())
    } catch (error) {
      console.error("Erreur lors de l'exportation des détails IN:", error)
    }
  }

  // Fonction pour formater les critères de filtrage de manière lisible
  const getFilterDescription = () => {
    const filters = []

    if (searchParams.get("statut") && searchParams.get("statut") !== "all") {
      filters.push(`Statut: ${searchParams.get("statut")}`)
    }

    if (searchParams.get("fa_statut") && searchParams.get("fa_statut") !== "all") {
      filters.push(`2FA Statut: ${searchParams.get("fa_statut")}`)
    }

    if (
      searchParams.get("limite_type") &&
      searchParams.get("limite_valeur") &&
      searchParams.get("limite_type") !== "none"
    ) {
      const operator = searchParams.get("limite_type") === "lt" ? "<" : ">"
      filters.push(`Pourcentage IN ${operator} ${searchParams.get("limite_valeur")}%`)
    }

    if (searchParams.get("date_min")) {
      filters.push(`Date min: ${new Date(searchParams.get("date_min")).toLocaleDateString()}`)
    }

    if (searchParams.get("date_max")) {
      filters.push(`Date max: ${new Date(searchParams.get("date_max")).toLocaleDateString()}`)
    }

    if (searchParams.get("annee") && searchParams.get("annee") !== "all") {
      filters.push(`Année: ${searchParams.get("annee")}`)
    }

    return filters
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Résultats</h2>
        <div className="flex gap-2">
          <Button onClick={handleExportInDetails} variant="outline" className="flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            Exporter détails IN
          </Button>
          <Button onClick={handleExport} variant="outline" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Exporter résumé
          </Button>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[200px]">Opérateur</TableHead>
              <TableHead>Nombre d'IN</TableHead>
              <TableHead>% IN (parc global)</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead>2FA_Statut</TableHead>
              <TableHead>Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center">
                  <div className="flex flex-col items-center justify-center">
                    <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin mb-2"></div>
                    <p className="text-sm text-muted-foreground">Chargement des données...</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-64">
                  <div className="flex flex-col items-center justify-center text-center p-6">
                    <AlertCircle className="h-12 w-12 text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium mb-2">Aucune donnée trouvée</h3>

                    {searchParams.toString() ? (
                      <>
                        <p className="text-muted-foreground mb-2">
                          Aucune donnée ne correspond aux critères de filtrage suivants:
                        </p>

                        <div className="bg-gray-50 p-3 rounded-md mb-4 text-sm">
                          {getFilterDescription().map((filter, index) => (
                            <div key={index} className="mb-1 last:mb-0">
                              {filter}
                            </div>
                          ))}
                        </div>

                        <p className="text-muted-foreground mb-4">
                          Essayez d'élargir vos critères de recherche pour obtenir plus de résultats.
                        </p>

                        <Button
                          variant="outline"
                          onClick={() => (window.location.href = "/")}
                          className="flex items-center gap-2"
                        >
                          <FilterX className="h-4 w-4" />
                          Réinitialiser les filtres
                        </Button>
                      </>
                    ) : (
                      <>
                        <p className="text-muted-foreground mb-4">
                          Aucune donnée n'est disponible. Commencez par charger des données.
                        </p>

                        <Button
                          variant="outline"
                          className="flex items-center gap-2"
                          onClick={() => {
                            // Trouver et cliquer sur le bouton d'importation dans la barre d'action
                            const importButton = document.querySelector(".action-bar-import-button")
                            if (importButton) {
                              ;(importButton as HTMLButtonElement).click()
                            }
                          }}
                        >
                          <Database className="h-4 w-4" />
                          Charger les données
                        </Button>
                      </>
                    )}
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              data.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">{row.operateur}</TableCell>
                  <TableCell>{row.nombre_in}</TableCell>
                  <TableCell>{row.pourcentage_in}%</TableCell>
                  <TableCell>{row.statut}</TableCell>
                  <TableCell>{row.fa_statut}</TableCell>
                  <TableCell>{new Date(row.date).toLocaleDateString()}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {data.length > 0 ? `Affichage de ${Math.min(10, data.length)} résultats par page` : "Aucun résultat"}
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page > 1 ? page - 1 : 1)}
            disabled={page === 1 || data.length === 0}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="text-sm font-medium">
            Page {page} sur {totalPages || 1}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={page === totalPages || totalPages === 0 || data.length === 0}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

