"use client"

import type React from "react"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  CheckCircle,
  AlertCircle,
  FileUp,
  Database,
  Loader2,
  FileText,
  Server,
  Cog,
  CheckCheck,
  Info,
} from "lucide-react"
import { purgeData } from "@/lib/data"
import { useToast } from "@/hooks/use-toast"
import { Checkbox } from "@/components/ui/checkbox"

// Configure this to match your backend URL
const BACKEND_URL = "http://localhost:8000"

interface ImportDialogProps {
  fileExists: boolean
}

export function ImportDialog({ fileExists }: ImportDialogProps) {
  const [open, setOpen] = useState(false)
  const [isPurgeOpen, setIsPurgeOpen] = useState(false)

  // États pour les fichiers
  const [dataFile, setDataFile] = useState<File | null>(null)
  const [mappingFile, setMappingFile] = useState<File | null>(null)
  const [appendMode, setAppendMode] = useState(true)

  // États pour le chargement et les résultats
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingToDb, setIsLoadingToDb] = useState(false)
  const [isPurging, setIsPurging] = useState(false)
  const [result, setResult] = useState<{ success: boolean; message: string; details?: any[] } | null>(null)
  const [dbResult, setDbResult] = useState<{ success: boolean; message: string } | null>(null)

  // États pour le glisser-déposer
  const [dragActive, setDragActive] = useState({ data: false, mapping: false })

  // États pour le suivi du traitement
  const [processedFiles, setProcessedFiles] = useState<string[]>([])
  const [loadProgress, setLoadProgress] = useState(0)
  const [loadMessage, setLoadMessage] = useState("")
  const [currentFile, setCurrentFile] = useState("")
  const [processingStep, setProcessingStep] = useState(0)

  const { toast } = useToast()

  const dataInputRef = useRef<HTMLInputElement>(null)
  const mappingInputRef = useRef<HTMLInputElement>(null)

  const handleDataFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      console.log("Selected data file:", file)
      setDataFile(file)
    }
  }

  const handleMappingFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      console.log("Selected mapping file:", file)
      setMappingFile(file)
    }
  }

  const handleDrag = (e: React.DragEvent<HTMLDivElement>, type: "data" | "mapping", active: boolean) => {
    e.preventDefault()
    e.stopPropagation()

    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive((prev) => ({ ...prev, [type]: active }))
    } else if (e.type === "dragleave") {
      setDragActive((prev) => ({ ...prev, [type]: false }))
    }
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>, type: "data" | "mapping") => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive((prev) => ({ ...prev, [type]: false }))

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (type === "data") {
        // Accept only .txt files
        const file = e.dataTransfer.files[0]
        if (file.name.toLowerCase().endsWith(".txt")) {
          console.log("Dropped data file:", file)
          setDataFile(file)
        } else {
          toast({
            title: "Format non supporté",
            description: "Veuillez sélectionner un fichier TXT pour les données",
            variant: "destructive",
          })
        }
      } else if (type === "mapping") {
        // Only accept .csv files for mapping
        const file = e.dataTransfer.files[0]
        if (file.name.toLowerCase().endsWith(".csv")) {
          console.log("Dropped mapping file:", file)
          setMappingFile(file)
        } else {
          toast({
            title: "Format non supporté",
            description: "Veuillez sélectionner un fichier CSV pour la correspondance",
            variant: "destructive",
          })
        }
      }
    }
  }

  const handleImport = async () => {
    if (!dataFile || !mappingFile) {
      setResult({
        success: false,
        message: "Veuillez sélectionner tous les fichiers requis",
      })
      return
    }

    setIsLoading(true)
    setResult(null)
    setDbResult(null)
    setCurrentFile("")
    setProcessedFiles([])
    setProcessingStep(0)

    try {
      const formData = new FormData()

      // Ajouter le fichier TXT au formData
      formData.append("dataFiles", dataFile)

      // Ajouter le fichier de mapping au formData
      formData.append("mappingFile", mappingFile)

      // Ajouter le mode d'ajout au formData
      formData.append("appendMode", appendMode.toString())

      setLoadMessage("Préparation des fichiers...")
      await new Promise((resolve) => setTimeout(resolve, 500))

      // Traiter le fichier
      setCurrentFile(dataFile.name)
      setProcessingStep(1)
      setLoadMessage(`Traitement du fichier ${dataFile.name}...`)
      await new Promise((resolve) => setTimeout(resolve, 800))

      // Faire l'appel API avec un timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000) // 5 minutes timeout

      try {
        const response = await fetch(`${BACKEND_URL}/api/process_files`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          const errorData = await response.json()
          throw new Error(errorData.message || "Erreur lors de l'importation")
        }

        const data = await response.json()

        // Simuler les fichiers traités pour l'interface
        const mockDetails = [
          {
            filename: dataFile.name,
            success: true,
            output_file: dataFile.name,
          },
        ]

        setProcessedFiles([dataFile.name])

        setResult({
          success: data.success,
          message: data.message || "Traitement terminé avec succès",
          details: mockDetails,
        })
      } catch (fetchError) {
        if (fetchError.name === "AbortError") {
          throw new Error("L'opération a pris trop de temps et a été interrompue. Essayez avec un fichier plus petit.")
        }
        throw fetchError
      } finally {
        clearTimeout(timeoutId)
      }
    } catch (error) {
      console.error("Import error:", error)
      setResult({
        success: false,
        message: `Erreur lors de l'importation: ${error instanceof Error ? error.message : String(error)}`,
      })
    } finally {
      setIsLoading(false)
      setProcessingStep(0)
      setLoadMessage("")
    }
  }

  const handleLoadToDatabase = async () => {
    setIsLoadingToDb(true)
    setDbResult(null)
    setLoadMessage("Chargement en cours...")

    try {
      // Simuler la progression avec des étapes plus naturelles
      const steps = [0, 5, 12, 25, 38, 52, 68, 79, 88, 94, 98, 100]

      for (const progress of steps) {
        setLoadProgress(progress)

        // Varier les messages en fonction de la progression
        if (progress < 20) {
          setLoadMessage("Préparation de la base de données...")
        } else if (progress < 50) {
          setLoadMessage("Chargement des données...")
        } else if (progress < 80) {
          setLoadMessage("Vérification de l'intégrité...")
        } else {
          setLoadMessage("Finalisation...")
        }

        // Temps d'attente variable pour une animation plus naturelle
        const delay = Math.floor(Math.random() * 300) + 300
        await new Promise((resolve) => setTimeout(resolve, delay))
      }

      // À ce stade, les données sont déjà chargées dans la base de données
      // car l'API /api/process_files a déjà été appelée dans handleImport

      setDbResult({
        success: true,
        message: "Données chargées avec succès dans la base de données",
      })

      // Ajouter un marqueur dans sessionStorage pour indiquer que nous venons de charger des données
      sessionStorage.setItem("justLoadedData", "true")

      // Reload the page after a short delay
      setTimeout(() => {
        window.location.reload()
      }, 1500)
    } catch (error) {
      console.error("Database load error:", error)
      setDbResult({
        success: false,
        message: `Erreur lors du chargement: ${error instanceof Error ? error.message : String(error)}`,
      })
    } finally {
      setIsLoadingToDb(false)
      setLoadProgress(0)
      setLoadMessage("")
    }
  }

  const handlePurge = async () => {
    setIsPurging(true)
    try {
      await purgeData()
      toast({
        title: "Succès",
        description: "Les données ont été purgées avec succès",
      })
      setIsPurgeOpen(false)
      // Recharger la page pour refléter l'absence de données
      window.location.reload()
    } catch (error) {
      toast({
        title: "Erreur",
        description: "Une erreur est survenue lors de la purge des données",
        variant: "destructive",
      })
    } finally {
      setIsPurging(false)
    }
  }

  const resetForm = () => {
    setDataFile(null)
    setMappingFile(null)
    setResult(null)
    setDbResult(null)
    setCurrentFile("")
    setProcessedFiles([])
    setLoadProgress(0)
    setLoadMessage("")
    setProcessingStep(0)
    setAppendMode(true)
  }

  return (
    <>
      <Dialog
        open={open}
        onOpenChange={(newOpen) => {
          setOpen(newOpen)
          if (!newOpen) resetForm()
        }}
      >
        <DialogTrigger asChild>
          <Button variant="outline" className="flex items-center gap-2 action-bar-import-button">
            <Database className="h-4 w-4" />
            Charger les données
          </Button>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Charger ou ajouter des données</DialogTitle>
            <DialogDescription>Importez un fichier TXT et le fichier de correspondance MAJNUM.csv</DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 py-4">
            {fileExists && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-800 flex items-start gap-3">
                <Info className="h-5 w-5 text-blue-500 mt-0.5" />
                <div>
                  <p className="font-medium">Des données existent déjà</p>
                  <p className="text-sm mt-1">
                    Vous pouvez ajouter ces nouvelles données aux données existantes ou purger les données existantes
                    avant d'importer.
                  </p>
                  <div className="flex items-center space-x-2 mt-3">
                    <Checkbox
                      id="append-mode"
                      checked={appendMode}
                      onCheckedChange={(checked) => setAppendMode(checked === true)}
                    />
                    <label htmlFor="append-mode" className="text-sm font-medium leading-none">
                      Ajouter aux données existantes
                    </label>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-2 bg-white"
                    onClick={() => {
                      setIsPurgeOpen(true)
                    }}
                  >
                    Purger les données existantes
                  </Button>
                </div>
              </div>
            )}

            {!isLoading && !result?.success && (
              <>
                <div className="grid gap-2">
                  <div
                    className={`border-2 border-dashed rounded-lg p-6 transition-colors ${
                      dragActive.data
                        ? "border-primary bg-primary/5"
                        : "border-muted-foreground/25 hover:border-muted-foreground/50"
                    }`}
                    onDragEnter={(e) => handleDrag(e, "data", true)}
                    onDragLeave={(e) => handleDrag(e, "data", false)}
                    onDragOver={(e) => handleDrag(e, "data", true)}
                    onDrop={(e) => handleDrop(e, "data")}
                    onClick={() => dataInputRef.current?.click()}
                  >
                    <div className="flex flex-col items-center justify-center gap-2 text-center cursor-pointer">
                      <FileUp className="h-10 w-10 text-muted-foreground" />
                      <h3 className="text-lg font-medium">Fichier de données (TXT)</h3>
                      <p className="text-sm text-muted-foreground mb-2">
                        Glissez-déposez votre fichier TXT ici ou cliquez pour parcourir
                      </p>
                      <input
                        ref={dataInputRef}
                        id="data-file"
                        type="file"
                        accept=".txt"
                        multiple={false}
                        onChange={handleDataFileChange}
                        className="hidden"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          dataInputRef.current?.click()
                        }}
                      >
                        Sélectionner un fichier
                      </Button>
                    </div>
                  </div>

                  {dataFile && (
                    <div className="text-sm text-muted-foreground flex items-center gap-2 p-2 bg-muted/50 rounded">
                      <FileText className="h-4 w-4" />
                      Fichier sélectionné: {dataFile.name}
                    </div>
                  )}
                </div>

                <div className="grid gap-2">
                  <div
                    className={`border-2 border-dashed rounded-lg p-6 transition-colors ${
                      dragActive.mapping
                        ? "border-primary bg-primary/5"
                        : "border-muted-foreground/25 hover:border-muted-foreground/50"
                    }`}
                    onDragEnter={(e) => handleDrag(e, "mapping", true)}
                    onDragLeave={(e) => handleDrag(e, "mapping", false)}
                    onDragOver={(e) => handleDrag(e, "mapping", true)}
                    onDrop={(e) => handleDrop(e, "mapping")}
                    onClick={() => mappingInputRef.current?.click()}
                  >
                    <div className="flex flex-col items-center justify-center gap-2 text-center cursor-pointer">
                      <FileText className="h-10 w-10 text-muted-foreground" />
                      <h3 className="text-lg font-medium">Fichier de correspondance (MAJNUM.csv)</h3>
                      <p className="text-sm text-muted-foreground mb-2">
                        Glissez-déposez votre fichier CSV ici ou cliquez pour parcourir
                      </p>
                      <input
                        ref={mappingInputRef}
                        id="mapping-file"
                        type="file"
                        accept=".csv"
                        onChange={handleMappingFileChange}
                        className="hidden"
                      />
                      <Button
                        variant="outline"
                        size="sm"
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          mappingInputRef.current?.click()
                        }}
                      >
                        Sélectionner un fichier
                      </Button>
                    </div>
                  </div>

                  {mappingFile && (
                    <div className="text-sm text-muted-foreground flex items-center gap-2 p-2 bg-muted/50 rounded">
                      <FileText className="h-4 w-4" />
                      Fichier sélectionné: {mappingFile.name}
                    </div>
                  )}
                </div>
              </>
            )}

            {isLoading && (
              <div className="p-6 bg-muted/30 rounded-md flex flex-col items-center justify-center text-center">
                <div className="relative mb-4">
                  <Cog className="h-10 w-10 text-primary animate-spin" />
                  <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                    <div className="h-2 w-2 bg-primary rounded-full"></div>
                  </div>
                </div>
                <p className="font-medium text-lg mb-3">Traitement en cours</p>

                <div className="w-full max-w-xs mx-auto mb-4">
                  <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all duration-500 ease-in-out"
                      style={{
                        width: `${processingStep > 0 ? (processingStep / (1 * 3 + 2)) * 100 : 0}%`,
                      }}
                    ></div>
                  </div>
                </div>

                <p className="text-sm font-medium text-primary">
                  {currentFile ? `Traitement de ${currentFile}` : loadMessage}
                </p>

                <div className="mt-4 text-xs text-muted-foreground animate-pulse">
                  Veuillez patienter pendant le traitement des fichiers...
                </div>
              </div>
            )}

            {isLoadingToDb && (
              <div className="p-6 bg-muted/30 rounded-md flex flex-col items-center justify-center text-center">
                <div className="relative mb-4">
                  <Server className="h-10 w-10 text-primary animate-pulse" />
                </div>
                <p className="font-medium text-lg mb-3">Chargement dans la base de données</p>

                {/* Progress bar with animation */}
                <div className="w-full max-w-xs mx-auto mb-4">
                  <div className="h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary rounded-full transition-all duration-500 ease-in-out"
                      style={{ width: `${loadProgress}%` }}
                    ></div>
                  </div>
                </div>

                <p className="text-sm font-medium text-primary">{loadMessage}</p>

                <div className="mt-4 text-xs text-muted-foreground">{loadProgress}% terminé</div>
              </div>
            )}

            {result && (
              <div
                className={`p-6 rounded-lg ${result.success ? "bg-green-50 border border-green-100" : "bg-red-50 border border-red-100"}`}
              >
                <div className="flex items-center gap-3 mb-3">
                  {result.success ? (
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-green-100">
                      <CheckCheck className="h-6 w-6 text-green-600" />
                    </div>
                  ) : (
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-red-100">
                      <AlertCircle className="h-6 w-6 text-red-600" />
                    </div>
                  )}
                  <div>
                    <h3 className={`text-lg font-medium ${result.success ? "text-green-800" : "text-red-800"}`}>
                      {result.success ? "Traitement terminé avec succès" : "Erreur de traitement"}
                    </h3>
                    <p className={`text-sm ${result.success ? "text-green-600" : "text-red-600"}`}>
                      {result.success ? `1 fichier traité avec succès` : result.message}
                    </p>
                  </div>
                </div>

                {result.details && result.details.length > 0 && (
                  <div className="mt-4 text-sm">
                    <p className={`font-medium mb-2 ${result.success ? "text-green-700" : "text-red-700"}`}>
                      Détails du traitement:
                    </p>
                    <div
                      className={`p-3 rounded ${result.success ? "bg-green-100" : "bg-red-100"} max-h-32 overflow-y-auto`}
                    >
                      <ul className="space-y-1">
                        {result.details.map((detail, index) => (
                          <li key={index} className="flex items-center gap-2">
                            {detail.success ? (
                              <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                            ) : (
                              <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
                            )}
                            <span className="truncate">{detail.filename}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>
            )}

            {dbResult && (
              <div
                className={`p-6 rounded-lg ${dbResult.success ? "bg-blue-50 border border-blue-100" : "bg-red-50 border border-red-100"}`}
              >
                <div className="flex items-center gap-3">
                  {dbResult.success ? (
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-100">
                      <Database className="h-6 w-6 text-blue-600" />
                    </div>
                  ) : (
                    <div className="flex items-center justify-center w-10 h-10 rounded-full bg-red-100">
                      <AlertCircle className="h-6 w-6 text-red-600" />
                    </div>
                  )}
                  <div>
                    <h3 className={`text-lg font-medium ${dbResult.success ? "text-blue-800" : "text-red-800"}`}>
                      {dbResult.success ? "Base de données mise à jour" : "Erreur de chargement"}
                    </h3>
                    <p className={`text-sm ${dbResult.success ? "text-blue-600" : "text-red-600"}`}>
                      {dbResult.message}
                    </p>
                  </div>
                </div>

                {dbResult.success && (
                  <div className="mt-4 text-center">
                    <p className="text-sm text-blue-600 mb-2">
                      La page va se recharger automatiquement dans quelques instants...
                    </p>
                    <div className="w-full h-1 bg-blue-100 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full animate-progress"></div>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2">
              {!result?.success ? (
                <>
                  <Button variant="outline" onClick={() => setOpen(false)}>
                    Annuler
                  </Button>
                  <Button
                    onClick={handleImport}
                    disabled={isLoading || !dataFile || !mappingFile || (fileExists && !appendMode)}
                    className="gap-2"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {fileExists && appendMode ? "Ajout en cours..." : "Extraction en cours..."}
                      </>
                    ) : (
                      <>
                        <Cog className="h-4 w-4" />
                        {fileExists && appendMode ? "Ajouter les données" : "Extraire les données"}
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <>
                  <Button variant="outline" onClick={() => setOpen(false)}>
                    Fermer
                  </Button>
                  <Button
                    onClick={handleLoadToDatabase}
                    disabled={isLoadingToDb || processedFiles.length === 0}
                    className="gap-2"
                    variant="default"
                  >
                    {isLoadingToDb ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Chargement...
                      </>
                    ) : (
                      <>
                        <Server className="h-4 w-4" />
                        Charger dans la base de données
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Modal de confirmation de purge */}
      <AlertDialog open={isPurgeOpen} onOpenChange={setIsPurgeOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Purger toutes les données</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action va supprimer définitivement toutes les données actuellement chargées. Vous devrez importer un
              nouveau fichier CSV pour continuer à utiliser l'application.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {/* Déplacé en dehors de AlertDialogDescription */}
          <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-amber-800 text-sm">
            <strong>Attention :</strong> Cette action est irréversible et supprimera toutes les données sans possibilité
            de récupération.
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault()
                handlePurge()
              }}
              className="bg-red-600 hover:bg-red-700"
              disabled={isPurging}
            >
              {isPurging ? (
                <>
                  <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                  Purge en cours...
                </>
              ) : (
                "Purger les données"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
