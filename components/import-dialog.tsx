"use client"

import { useState, useRef } from "react"
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
import { Upload, FileText, CheckCircle, AlertCircle, FileUp, Database } from "lucide-react"
import { importData } from "@/lib/import"

export function ImportDialog() {
  const [dataFiles, setDataFiles] = useState([])
  const [mappingFile, setMappingFile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [dragActive, setDragActive] = useState({ data: false, mapping: false })
  const [open, setOpen] = useState(false)

  const dataInputRef = useRef(null)
  const mappingInputRef = useRef(null)

  const handleDataFilesChange = (e) => {
    const files = Array.from(e.target.files)
    setDataFiles(files)
  }

  const handleMappingFileChange = (e) => {
    const file = e.target.files[0]
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
        setDataFiles(Array.from(e.dataTransfer.files))
      } else if (type === "mapping") {
        setMappingFile(e.dataTransfer.files[0])
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

    try {
      const formData = new FormData()

      dataFiles.forEach((file, index) => {
        formData.append(`dataFiles`, file)
      })

      formData.append("mappingFile", mappingFile)

      // Appel à la fonction d'importation simulée
      const response = await importData(formData)

      setResult({
        success: true,
        message: `Importation réussie: ${response.rowsImported} lignes importées (simulation)`,
      })

      // Réinitialiser les fichiers après une importation réussie
      if (response.success) {
        setTimeout(() => {
          setDataFiles([])
          setMappingFile(null)
          // Fermer le dialogue après 2 secondes pour montrer le message de succès
          setTimeout(() => {
            setOpen(false)
            setResult(null)
          }, 2000)
        }, 500)
      }
    } catch (error) {
      setResult({
        success: false,
        message: `Erreur lors de l'importation: ${error.message}`,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const resetForm = () => {
    setDataFiles([])
    setMappingFile(null)
    setResult(null)
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

          {result && (
            <Alert variant={result.success ? "default" : "destructive"}>
              {result.success ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
              <AlertTitle>{result.success ? "Succès" : "Erreur"}</AlertTitle>
              <AlertDescription>{result.message}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleImport} disabled={isLoading || dataFiles.length === 0 || !mappingFile}>
              {isLoading ? (
                "Importation en cours..."
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Importer les données
                </>
              )}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

