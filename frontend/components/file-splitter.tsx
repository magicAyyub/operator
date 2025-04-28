"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { Scissors, FileText, CheckCircle, AlertCircle } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

interface FileSplitterProps {
  file: File
  onSplitComplete: (files: File[]) => void
  onCancel: () => void
}

export default function FileSplitter({ file, onSplitComplete, onCancel }: FileSplitterProps) {
  const [splitting, setSplitting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [parts, setParts] = useState<number>(2)
  const [splitFiles, setSplitFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

  // Calculate optimal number of parts based on file size
  const calculateOptimalParts = () => {
    const sizeInGB = file.size / (1024 * 1024 * 1024)
    if (sizeInGB > 3) return 4
    if (sizeInGB > 2) return 3
    return 2
  }

  // Split the file into multiple parts with header preservation
  const splitFileSimple = async () => {
    setSplitting(true)
    setProgress(0)
    setError(null)

    try {
      const optimalParts = parts || calculateOptimalParts()
      const splitFiles: File[] = []

      // Lire le début du fichier pour extraire l'en-tête
      const headerReader = new FileReader()
      const headerPromise = new Promise<string>((resolve, reject) => {
        headerReader.onload = (e) => {
          const content = e.target?.result as string
          // Trouver la première ligne qui sera utilisée comme en-tête
          const firstLineEnd = content.indexOf("\n")
          if (firstLineEnd === -1) {
            resolve(content) // Pas de saut de ligne trouvé, utiliser tout le contenu
          } else {
            resolve(content.substring(0, firstLineEnd + 1)) // Inclure le saut de ligne
          }
        }
        headerReader.onerror = (e) => {
          reject(new Error("Erreur lors de la lecture de l'en-tête: " + headerReader.error?.message))
        }
        // Lire seulement les premiers Ko du fichier pour trouver l'en-tête
        headerReader.readAsText(file.slice(0, 10240))
      })

      // Attendre que l'en-tête soit lu
      const header = await headerPromise
      console.log("En-tête extrait:", header)

      // Simple approach: divide the file into equal parts
      const contentSize = file.size
      const partSize = Math.ceil(contentSize / optimalParts)

      for (let i = 0; i < optimalParts; i++) {
        setProgress(Math.round((i / optimalParts) * 100))

        // Calculer les positions de début et fin pour le contenu
        const start = i * partSize
        const end = Math.min(file.size, (i + 1) * partSize)

        // Créer un blob qui combine l'en-tête et le contenu de cette partie
        let partBlob

        if (i === 0) {
          // Pour la première partie, pas besoin d'ajouter l'en-tête car il y est déjà
          partBlob = file.slice(start, end)
        } else {
          // Pour les parties suivantes, ajouter l'en-tête au début
          // Convertir l'en-tête en Blob
          const headerBlob = new Blob([header], { type: "text/plain" })

          // Créer un blob pour le contenu de cette partie
          const contentBlob = file.slice(start, end)

          // Combiner l'en-tête et le contenu
          partBlob = new Blob([headerBlob, contentBlob], { type: file.type })
        }

        const fileName = `${file.name.replace(/\.[^/.]+$/, "")}_part${i + 1}${file.name.match(/\.[^/.]+$/)?.[0] || ""}`
        const partFile = new File([partBlob], fileName, { type: file.type })

        splitFiles.push(partFile)

        // Small delay to allow UI to update
        await new Promise((resolve) => setTimeout(resolve, 100))
      }

      setProgress(100)
      setSplitFiles(splitFiles)

      toast({
        title: "Fichier divisé avec succès",
        description: `Le fichier a été divisé en ${splitFiles.length} parties avec l'en-tête préservé dans chaque partie.`,
      })

      onSplitComplete(splitFiles)
    } catch (error) {
      console.error("Error splitting file:", error)
      setError(error instanceof Error ? error.message : "Une erreur inconnue s'est produite")
      toast({
        title: "Erreur",
        description: "Une erreur est survenue lors de la division du fichier.",
        variant: "destructive",
      })
    } finally {
      setSplitting(false)
    }
  }

  return (
    <div className="space-y-4 p-4 border rounded-lg bg-muted/20">
      <div className="flex items-start gap-3">
        <div className="bg-primary/10 p-2 rounded-full">
          <Scissors className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h3 className="text-lg font-medium">Division du fichier</h3>
          <p className="text-sm text-muted-foreground">
            Nous allons diviser <span className="font-medium">{file.name}</span> en plusieurs parties pour faciliter le
            traitement.
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-500 mt-0.5" />
          <div>
            <p className="font-medium">Erreur lors de la division du fichier</p>
            <p className="text-sm mt-1">{error}</p>
            <p className="text-sm mt-2">Essayez avec un fichier plus petit ou contactez le support technique.</p>
          </div>
        </div>
      )}

      {!splitting && splitFiles.length === 0 && (
        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="parts" className="text-sm font-medium">
              Nombre de parties
            </label>
            <select
              id="parts"
              className="w-full rounded-md border border-input bg-background px-3 py-2"
              value={parts}
              onChange={(e) => setParts(Number.parseInt(e.target.value))}
            >
              <option value={2}>2 parties</option>
              <option value={3}>3 parties</option>
              <option value={4}>4 parties</option>
              <option value={5}>5 parties</option>
            </select>
            <p className="text-xs text-muted-foreground">
              Recommandation: {calculateOptimalParts()} parties pour un fichier de{" "}
              {(file.size / (1024 * 1024 * 1024)).toFixed(2)} GB
            </p>
          </div>

          <div className="flex flex-col sm:flex-row justify-end gap-2">
            <Button variant="outline" onClick={onCancel}>
              Annuler
            </Button>
            <Button onClick={splitFileSimple} className="gap-2">
              <Scissors className="h-4 w-4" />
              Diviser le fichier
            </Button>
          </div>
        </div>
      )}

      {splitting && (
        <div className="space-y-4">
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Progression</span>
              <span>{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
          </div>
          <p className="text-sm text-center text-muted-foreground animate-pulse">Division du fichier en cours...</p>
        </div>
      )}

      {!splitting && splitFiles.length > 0 && (
        <div className="space-y-4">
          <div className="rounded-lg border bg-card p-3">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              <h4 className="font-medium">Fichier divisé avec succès</h4>
            </div>
            <ul className="space-y-2">
              {splitFiles.map((file, index) => (
                <li key={index} className="flex items-center gap-2 text-sm">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="flex-1 truncate">{file.name}</span>
                  <span className="text-xs text-muted-foreground">{(file.size / (1024 * 1024)).toFixed(2)} MB</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex justify-end">
            <Button onClick={() => onSplitComplete(splitFiles)} className="gap-2">
              <CheckCircle className="h-4 w-4" />
              Utiliser ces fichiers
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
