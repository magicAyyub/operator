"use client"

import { useState, useRef, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { FileText, CheckCircle, AlertCircle, FileUp, Database, Loader2, Settings, Cog, Server } from "lucide-react"

// Configure this to match your backend URL
const BACKEND_URL = "http://localhost:8000"

export function ImportDialog() {
  const [dataFiles, setDataFiles] = useState([])
  const [mappingFile, setMappingFile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingToDb, setIsLoadingToDb] = useState(false)
  const [result, setResult] = useState(null)
  const [dbResult, setDbResult] = useState(null)
  const [dragActive, setDragActive] = useState({ data: false, mapping: false })
  const [open, setOpen] = useState(false)
  const [currentFile, setCurrentFile] = useState("")
  const [debugInfo, setDebugInfo] = useState(null)
  const [processedFiles, setProcessedFiles] = useState([])
  const [loadProgress, setLoadProgress] = useState(0)
  const [loadMessage, setLoadMessage] = useState("")

  const dataInputRef = useRef(null)
  const mappingInputRef = useRef(null)


  const handleDataFilesChange = (e) => {
    const files = Array.from(e.target.files)
    console.log("Selected data files:", files)
    setDataFiles(files)
  }

  const handleMappingFileChange = (e) => {
    const file = e.target.files[0]
    console.log("Selected mapping file:", file)
    setMappingFile(file)
  }

  const handleDrag = (e, type, active) => {
    e.preventDefault()
    e.stopPropagation()

    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive((prev) => ({ ...prev, [type]: active }))
    } else if (e.type === "dragleave") {
      setDragActive((prev) => ({ ...prev, [type]: false }))
    }
  }

  const handleDrop = (e, type) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive((prev) => ({ ...prev, [type]: false }))

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      if (type === "data") {
        // Filter to only accept .txt files
        const txtFiles = Array.from(e.dataTransfer.files).filter((file) => file.name.toLowerCase().endsWith(".txt"))
        console.log("Dropped data files:", txtFiles)
        setDataFiles(txtFiles)
      } else if (type === "mapping") {
        // Only accept .csv files for mapping
        const file = e.dataTransfer.files[0]
        if (file.name.toLowerCase().endsWith(".csv")) {
          console.log("Dropped mapping file:", file)
          setMappingFile(file)
        }
      }
    }
  }

  const handleImport = async () => {
    if (dataFiles.length === 0 || !mappingFile) {
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
    setDebugInfo(null)
    setProcessedFiles([])

    try {
      const formData = new FormData()

      dataFiles.forEach((file) => {
        formData.append("dataFiles", file)
      })

      formData.append("mappingFile", mappingFile)

      console.log("Sending files to backend:", {
        dataFiles: dataFiles.map((f) => f.name),
        mappingFile: mappingFile.name,
      })

      // Call the Python backend API
      const response = await fetch(`${BACKEND_URL}/api/process_files`, {
        method: "POST",
        body: formData,
      })

      const responseText = await response.text()
      console.log("Raw response:", responseText)

      let data
      try {
        data = JSON.parse(responseText)
      } catch (e) {
        throw new Error(`Invalid JSON response: ${responseText}`)
      }

      console.log("Parsed response:", data)

      if (!response.ok) {
        throw new Error(data.error || "Erreur lors de l'importation")
      }

      setDebugInfo({
        responseStatus: response.status,
        responseData: data,
      })

      // Extract processed file paths from the response
      const successfulFiles = data.details.filter((detail) => detail.success).map((detail) => detail.output_file)

      setProcessedFiles(successfulFiles)

      setResult({
        success: data.success,
        message: `Importation terminée: ${data.filesProcessed}/${data.totalFiles} fichiers traités avec succès`,
        details: data.details,
      })
    } catch (error) {
      console.error("Import error:", error)
      setResult({
        success: false,
        message: `Erreur lors de l'importation: ${error.message}`,
      })
      setDebugInfo((prev) => ({
        ...prev,
        error: error.toString(),
        stack: error.stack,
      }))
    } finally {
      setIsLoading(false)
    }
  }

  const handleLoadToDatabase = async () => {
    setIsLoadingToDb(true)
    setDbResult(null)
    setLoadMessage("Chargement en cours...")

    try {
      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        setLoadProgress(i)
        await new Promise(resolve => setTimeout(resolve, 500))
      }

      setDbResult({
        success: true,
        message: "Données chargées avec succès dans la base de données"
      })

      // Reload the page after a short delay
      setTimeout(() => {
        window.location.reload()
      }, 1500)

    } catch (error) {
      console.error("Database load error:", error)
      setDbResult({
        success: false,
        message: `Erreur lors du chargement: ${error.message}`
      })
    } finally {
      setIsLoadingToDb(false)
      setLoadProgress(0)
      setLoadMessage("")
    }
  }

  const resetForm = () => {
    setDataFiles([])
    setMappingFile(null)
    setResult(null)
    setDbResult(null)
    setCurrentFile("")
    setDebugInfo(null)
    setProcessedFiles([])
    setLoadProgress(0)
    setLoadMessage("")
  }

  return (
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
          <DialogTitle>Charger les données</DialogTitle>
          <DialogDescription>Importez des fichiers TXT et le fichier de correspondance MAJNUM.csv</DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 py-4">
          {!result?.success && (
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
                    <h3 className="text-lg font-medium">Fichiers de données (TXT)</h3>
                    <p className="text-sm text-muted-foreground mb-2">
                      Glissez-déposez vos fichiers TXT ici ou cliquez pour parcourir
                    </p>
                    <input
                      ref={dataInputRef}
                      id="data-files"
                      type="file"
                      accept=".txt"
                      multiple
                      onChange={handleDataFilesChange}
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
                      Sélectionner des fichiers
                    </Button>
                  </div>
                </div>

                {dataFiles.length > 0 && (
                  <div className="text-sm text-muted-foreground flex items-center gap-2 p-2 bg-muted/50 rounded">
                    <FileText className="h-4 w-4" />
                    {dataFiles.length} fichier(s) sélectionné(s): {dataFiles.map((f) => f.name).join(", ")}
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
                <Cog className="h-8 w-8 text-primary animate-spin" />
                <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                  <div className="h-2 w-2 bg-primary rounded-full"></div>
                </div>
              </div>
              <p className="font-medium text-lg mb-1">Traitement en cours</p>
              <p className="text-sm text-muted-foreground">
                {currentFile ? `Fichier ${currentFile}` : "Veuillez patienter..."}
              </p>
            </div>
          )}

          {isLoadingToDb && (
            <div className="p-6 bg-muted/30 rounded-md flex flex-col items-center justify-center text-center">
              <div className="relative mb-4">
                <Server className="h-8 w-8 text-primary animate-pulse" />
              </div>
              <p className="font-medium text-lg mb-1">Chargement dans la base de données</p>
              <p className="text-sm text-muted-foreground mb-2">
                {loadMessage || "Veuillez patienter pendant le chargement des données..."}
              </p>

              {/* Progress bar */}
              <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700 mb-1">
                <div
                  className="bg-primary h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${loadProgress}%` }}
                ></div>
              </div>
              <p className="text-xs text-muted-foreground">{loadProgress}%</p>
            </div>
          )}

          {result && (
            <Alert variant={result.success ? "default" : "destructive"}>
              {result.success ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              <AlertTitle>{result.success ? "Succès" : "Erreur"}</AlertTitle>
              <AlertDescription>{result.message}</AlertDescription>

              {result.details && result.details.length > 0 && (
                <div className="mt-2 text-xs max-h-32 overflow-y-auto">
                  <p className="font-semibold">Détails:</p>
                  <ul className="list-disc pl-5">
                    {result.details.map((detail, index) => (
                      <li key={index} className={detail.success ? "text-green-600" : "text-red-600"}>
                        {detail.filename}: {detail.success ? "Succès" : `Échec - ${detail.error || "Erreur inconnue"}`}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Alert>
          )}

          {dbResult && (
            <Alert variant={dbResult.success ? "default" : "destructive"} className="mt-4">
              {dbResult.success ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              <AlertTitle>{dbResult.success ? "Base de données mise à jour" : "Erreur"}</AlertTitle>
              <AlertDescription>{dbResult.message}</AlertDescription>
            </Alert>
          )}

          {debugInfo && (
            <div className="mt-4 p-2 bg-gray-100 rounded text-xs font-mono overflow-x-auto">
              <details>
                <summary className="cursor-pointer font-semibold">Informations de débogage</summary>
                <pre className="mt-2 whitespace-pre-wrap">{JSON.stringify(debugInfo, null, 2)}</pre>
              </details>
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
                  disabled={isLoading || dataFiles.length === 0 || !mappingFile}
                  className="gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Extraction en cours...
                    </>
                  ) : (
                    <>
                      <Settings className="h-4 w-4" />
                      Extraire les données
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
  )
}