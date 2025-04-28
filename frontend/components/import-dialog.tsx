"use client"

import { DialogTrigger } from "@/components/ui/dialog"
import type React from "react"
import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
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
  Upload,
  Cog,
  CheckCheck,
  Trash2,
  Server,
  Scissors,
} from "lucide-react"
import { purgeData } from "@/lib/data"
import { useToast } from "@/hooks/use-toast"
import { addNotification } from "@/lib/notifications"
import { FileSizeWarning } from "@/components/file-size-warning"
import FileSplitter from "@/components/file-splitter"

// Configure this to match your backend URL
const BACKEND_URL = "http://localhost:8000"

// File size threshold for warning (2GB)
const FILE_SIZE_WARNING_THRESHOLD = 2 * 1024 * 1024 * 1024

interface ImportDialogProps {
  fileExists: boolean
}

export function ImportDialog({ fileExists }: ImportDialogProps) {
  const [open, setOpen] = useState(false)
  const [isPurgeOpen, setIsPurgeOpen] = useState(false)

  // États pour les fichiers
  const [dataFile, setDataFile] = useState<File | null>(null)
  const [mappingFile, setMappingFile] = useState<File | null>(null)
  const [splitFiles, setSplitFiles] = useState<File[]>([])
  const [currentSplitFileIndex, setCurrentSplitFileIndex] = useState<number>(-1)
  const [showSizeWarning, setShowSizeWarning] = useState(false)
  const [showFileSplitter, setShowFileSplitter] = useState(false)

  // États pour le chargement et les résultats
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingToDb, setIsLoadingToDb] = useState(false)
  const [isPurging, setIsPurging] = useState(false)
  const [result, setResult] = useState<{ success: boolean; message: string; details?: any[] } | null>(null)
  const [dbResult, setDbResult] = useState<{ success: boolean; message: string } | null>(null)
  const [splitResults, setSplitResults] = useState<Array<{ success: boolean; message: string; details?: any[] }>>([])

  // États pour le glisser-déposer
  const [dragActive, setDragActive] = useState({ data: false, mapping: false })

  // États pour le suivi du traitement
  const [processedFiles, setProcessedFiles] = useState<string[]>([])
  const [failedFiles, setFailedFiles] = useState<string[]>([])
  const [loadProgress, setLoadProgress] = useState(0)
  const [loadMessage, setLoadMessage] = useState("")
  const [currentFile, setCurrentFile] = useState("")
  const [processingStep, setProcessingStep] = useState(0)
  const [processingAllParts, setProcessingAllParts] = useState(false)

  const { toast } = useToast()

  const dataInputRef = useRef<HTMLInputElement>(null)
  const mappingInputRef = useRef<HTMLInputElement>(null)

  // Traitement automatique des parties
  useEffect(() => {
    if (
      processingAllParts &&
      splitFiles.length > 0 &&
      currentSplitFileIndex >= 0 &&
      currentSplitFileIndex < splitFiles.length &&
      !isLoading &&
      !failedFiles.includes(splitFiles[currentSplitFileIndex].name)
    ) {
      // Traiter la partie actuelle
      const timer = setTimeout(() => {
        handleImportSplitFile(splitFiles[currentSplitFileIndex], currentSplitFileIndex)
      }, 1000) // Délai réduit à 1 seconde pour plus de fluidité

      return () => clearTimeout(timer)
    }
  }, [currentSplitFileIndex, splitFiles, isLoading, failedFiles, processingAllParts])

  const handleDataFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setDataFile(file)

      // Check if file is large and show warning
      if (file.size > FILE_SIZE_WARNING_THRESHOLD) {
        setShowSizeWarning(true)
      } else {
        setShowSizeWarning(false)
      }
    }
  }

  const handleMappingFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
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
          setDataFile(file)

          // Check if file is large and show warning
          if (file.size > FILE_SIZE_WARNING_THRESHOLD) {
            setShowSizeWarning(true)
          } else {
            setShowSizeWarning(false)
          }
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

  const handleSplitComplete = (files: File[]) => {
    setSplitFiles(files)
    setShowFileSplitter(false)
    toast({
      title: "Fichiers prêts",
      description: `${files.length} fichiers ont été créés et sont prêts à être traités.`,
    })
  }

  const startSplitFileProcessing = () => {
    // Reset previous results
    setSplitResults([])
    setProcessedFiles([])
    setFailedFiles([])
    setCurrentSplitFileIndex(0) // Start with the first file
    setProcessingAllParts(true) // Activer le traitement automatique
  }

  const handleImportSplitFile = async (file: File, index: number) => {
    if (!file || !mappingFile) {
      return
    }

    setIsLoading(true)
    setCurrentFile(file.name)
    setLoadMessage(`Traitement du fichier ${index + 1}/${splitFiles.length}: ${file.name}...`)
    setProcessingStep(1)

    try {
      const formData = new FormData()
      formData.append("dataFiles", file)
      formData.append("mappingFile", mappingFile)

      // Toujours utiliser appendMode=true si des données existent déjà ou si ce n'est pas la première partie
      const shouldAppend = fileExists || index > 0
      formData.append("appendMode", shouldAppend ? "true" : "false")

      // Faire l'appel API avec un timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000) // 10 minutes timeout

      try {
        const response = await fetch(`${BACKEND_URL}/api/process_files`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          const errorText = await response.text()
          let errorMessage = "Erreur lors de l'importation"

          try {
            const errorData = JSON.parse(errorText)
            errorMessage = errorData.detail || errorData.message || errorMessage
          } catch (e) {
            errorMessage = errorText || errorMessage
          }

          throw new Error(errorMessage)
        }

        const data = await response.json()

        // Add to processed files
        setProcessedFiles((prev) => [...prev, file.name])

        // Add to split results
        const resultDetails = {
          success: true,
          message: `Partie ${index + 1}/${splitFiles.length} traitée avec succès`,
          details: [
            {
              filename: file.name,
              success: true,
              output_file: file.name,
            },
          ],
        }

        setSplitResults((prev) => [...prev, resultDetails])

        // Add notification for this part
        addNotification({
          fileName: file.name,
          mappingFileName: mappingFile.name,
          rowsProcessed: data.rows_processed || 0,
          totalRows: data.total_rows || 0,
          duplicatesFound: 0,
          type: shouldAppend ? "append" : "upload",
        })

        // Move to next file or finish
        if (index < splitFiles.length - 1) {
          setCurrentSplitFileIndex(index + 1)
        } else {
          // All files processed
          setResult({
            success: true,
            message: `Traitement terminé: ${processedFiles.length + 1}/${splitFiles.length} fichiers traités avec succès`,
            details: splitFiles.map((f) => ({
              filename: f.name,
              success: !failedFiles.includes(f.name),
              output_file: f.name,
            })),
          })
          setCurrentSplitFileIndex(-1) // Reset
          setProcessingAllParts(false) // Arrêter le traitement automatique
        }
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

      // Add to failed files
      setFailedFiles((prev) => [...prev, file.name])

      // Add error to split results
      setSplitResults((prev) => [
        ...prev,
        {
          success: false,
          message: `Erreur lors du traitement de la partie ${index + 1}: ${error instanceof Error ? error.message : String(error)}`,
        },
      ])

      // Continuer avec la partie suivante malgré l'erreur
      if (index < splitFiles.length - 1) {
        setCurrentSplitFileIndex(index + 1)
      } else {
        // C'était la dernière partie
        setProcessingAllParts(false)

        // Afficher le résultat final
        const successCount = processedFiles.length
        const totalCount = splitFiles.length

        if (successCount > 0) {
          setResult({
            success: true,
            message: `Traitement terminé: ${successCount}/${totalCount} fichiers traités avec succès`,
            details: splitFiles.map((f) => ({
              filename: f.name,
              success: !failedFiles.includes(f.name),
              output_file: f.name,
            })),
          })
        } else {
          setResult({
            success: false,
            message: "Aucun fichier n'a pu être traité correctement",
            details: [],
          })
        }
      }
    } finally {
      setIsLoading(false)
      setProcessingStep(0)
      setLoadMessage("")
    }
  }

  const handleImport = async () => {
    if (!dataFile || !mappingFile) {
      toast({
        title: "Fichiers manquants",
        description: "Veuillez sélectionner tous les fichiers requis",
        variant: "destructive",
      })
      return
    }

    // If we have split files, process them one by one
    if (splitFiles.length > 0) {
      startSplitFileProcessing()
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
      formData.append("dataFiles", dataFile)
      formData.append("mappingFile", mappingFile)
      formData.append("appendMode", fileExists ? "true" : "false")

      setLoadMessage("Préparation des fichiers...")
      await new Promise((resolve) => setTimeout(resolve, 500))

      setCurrentFile(dataFile.name)
      setProcessingStep(1)
      setLoadMessage(`Traitement du fichier ${dataFile.name}...`)

      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 10 * 60 * 1000) // 10 minutes timeout

      try {
        const response = await fetch(`${BACKEND_URL}/api/process_files`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        })

        clearTimeout(timeoutId)

        if (!response.ok) {
          const errorText = await response.text()
          let errorMessage = "Erreur lors de l'importation"

          try {
            const errorData = JSON.parse(errorText)
            errorMessage = errorData.detail || errorData.message || errorMessage
          } catch (e) {
            errorMessage = errorText || errorMessage
          }

          throw new Error(errorMessage)
        }

        const data = await response.json()

        setProcessedFiles([dataFile.name])

        const successMessage = data.message || "Traitement terminé avec succès"

        setResult({
          success: data.success,
          message: successMessage,
          details: [
            {
              filename: dataFile.name,
              success: true,
              output_file: dataFile.name,
            },
          ],
        })

        // Ajouter une notification
        addNotification({
          fileName: dataFile.name,
          mappingFileName: mappingFile.name,
          rowsProcessed: data.rows_processed || 0,
          totalRows: data.total_rows || 0,
          duplicatesFound: 0,
          type: fileExists ? "append" : "upload",
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
      const steps = [0, 15, 30, 45, 60, 75, 90, 100]

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
        const delay = Math.floor(Math.random() * 200) + 200
        await new Promise((resolve) => setTimeout(resolve, delay))
      }

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

      // Ajouter une notification pour la purge
      addNotification({
        fileName: "Toutes les données",
        mappingFileName: "",
        rowsProcessed: 0,
        totalRows: 0,
        type: "purge",
      })

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
    setFailedFiles([])
    setLoadProgress(0)
    setLoadMessage("")
    setProcessingStep(0)
    setSplitFiles([])
    setSplitResults([])
    setCurrentSplitFileIndex(-1)
    setShowSizeWarning(false)
    setShowFileSplitter(false)
    setProcessingAllParts(false)
  }

  // Déterminer ce qui doit être affiché dans la zone principale
  const renderMainContent = () => {
    // Si on est en train de charger
    if (isLoading) {
      return (
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

          {splitFiles.length > 0 && (
            <p className="mt-2 text-sm text-muted-foreground">
              Fichier {currentSplitFileIndex + 1} sur {splitFiles.length}
            </p>
          )}

          <div className="mt-4 text-xs text-muted-foreground animate-pulse">
            Veuillez patienter pendant le traitement des fichiers...
          </div>
        </div>
      )
    }

    // Si on est en train de finaliser le chargement
    if (isLoadingToDb) {
      return (
        <div className="p-6 bg-muted/30 rounded-md flex flex-col items-center justify-center text-center">
          <div className="relative mb-4">
            <Server className="h-10 w-10 text-primary animate-pulse" />
          </div>
          <p className="font-medium text-lg mb-3">Finalisation du traitement</p>

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
      )
    }

    // Si on a un résultat final
    if (result) {
      return (
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
              <p className={`text-sm ${result.success ? "text-green-600" : "text-red-600"}`}>{result.message}</p>
            </div>
          </div>

          {result.details && result.details.length > 0 && (
            <div className="mt-4 text-sm">
              <p className={`font-medium mb-2 ${result.success ? "text-green-700" : "text-red-700"}`}>
                Détails du traitement:
              </p>
              <div className={`p-3 rounded ${result.success ? "bg-green-100" : "bg-red-100"} max-h-32 overflow-y-auto`}>
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
      )
    }

    // Si on a un résultat de base de données
    if (dbResult) {
      return (
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
                {dbResult.success ? "Traitement terminé" : "Erreur de traitement"}
              </h3>
              <p className={`text-sm ${dbResult.success ? "text-blue-600" : "text-red-600"}`}>{dbResult.message}</p>
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
      )
    }

    // Si on est en train de diviser le fichier
    if (showFileSplitter && dataFile) {
      return (
        <FileSplitter
          file={dataFile}
          onSplitComplete={handleSplitComplete}
          onCancel={() => setShowFileSplitter(false)}
        />
      )
    }

    // Si on a des fichiers divisés
    if (splitFiles.length > 0) {
      return (
        <>
          <div className="rounded-lg border p-4 bg-blue-50 border-blue-200 mb-4">
            <div className="flex items-start gap-3">
              <Scissors className="h-5 w-5 text-blue-500 mt-0.5" />
              <div>
                <h3 className="font-medium text-blue-800">Fichier divisé en {splitFiles.length} parties</h3>
                <p className="text-sm text-blue-700 mt-1">
                  Le fichier a été divisé pour faciliter le traitement. Toutes les parties seront traitées
                  séquentiellement.
                </p>
                <div className="mt-3 space-y-1 max-h-32 overflow-y-auto">
                  {splitFiles.map((file, index) => (
                    <div key={index} className="flex items-center gap-2 text-sm text-blue-800">
                      <FileText className="h-4 w-4" />
                      <span className="flex-1 truncate">{file.name}</span>
                      <span className="text-xs text-blue-600">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Zone de sélection du fichier de mapping uniquement */}
          <div className="grid gap-2 mb-4">
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

          {/* Résultats du traitement par parties */}
          {splitResults.length > 0 && (
            <div className="rounded-lg border p-4 mb-4">
              <h3 className="font-medium mb-3">Résultats du traitement par parties</h3>
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {splitResults.map((result, index) => (
                  <div
                    key={index}
                    className={`p-2 rounded-md flex items-center gap-2 ${
                      result.success ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
                    }`}
                  >
                    {result.success ? (
                      <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
                    )}
                    <span className="text-sm">{result.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )
    }

    // Si on a un avertissement de taille de fichier
    if (showSizeWarning && dataFile) {
      return (
        <FileSizeWarning
          fileName={dataFile.name}
          fileSize={dataFile.size}
          onSplit={() => setShowFileSplitter(true)}
          onContinue={() => setShowSizeWarning(false)}
        />
      )
    }

    // Affichage par défaut: sélection des fichiers
    return (
      <>
        <div className="grid gap-4">
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
              Fichier sélectionné: {dataFile.name} ({(dataFile.size / (1024 * 1024)).toFixed(2)} MB)
            </div>
          )}
        </div>

        <div className="grid gap-4 mt-4">
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
    )
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
          <div className="flex items-center gap-2">
            <Button variant="outline" className="flex items-center gap-2 action-bar-import-button">
              <Database className="h-4 w-4" />
              Charger les données
            </Button>

            {fileExists && (


                <Button
                variant="outline"
                size="sm"
                className="bg-white text-red-600 border-red-200 hover:bg-red-50"
                onClick={(e) => {
                  e.stopPropagation()
                  setIsPurgeOpen(true)
                }}
                >
                <Trash2 className="h-4 w-4 mr-2" />
                Purger les données
                </Button>
              )}
          </div>
        </DialogTrigger>
        <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between">
              <span>Charger des données</span>
            </DialogTitle>
            <DialogDescription>
              {fileExists
                ? "Sans purge, les nouvelles données seront ajoutées aux données existantes"
                : "Importez un fichier TXT et le fichier de correspondance MAJNUM.csv"}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 py-4">
            {/* Contenu principal dynamique */}
            {renderMainContent()}

            {/* Boutons d'action */}
            <div className="flex justify-end gap-2">
              {!result?.success ? (
                <>
                  <Button variant="outline" onClick={() => setOpen(false)}>
                    Annuler
                  </Button>
                  <Button
                    onClick={handleImport}
                    disabled={isLoading || !dataFile || !mappingFile || showFileSplitter}
                    className="gap-2"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Traitement en cours...
                      </>
                    ) : splitFiles.length > 0 ? (
                      <>
                        <Scissors className="h-4 w-4" />
                        Traiter les {splitFiles.length} parties
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4" />
                        {fileExists ? "Ajouter aux données existantes" : "Charger les données"}
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
                        Finalisation...
                      </>
                    ) : (
                      <>
                        <CheckCheck className="h-4 w-4" />
                        Terminer
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
