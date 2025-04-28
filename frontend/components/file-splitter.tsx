"use client"

// FileSplitter.tsx
import type React from "react"
import { useState, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { useToast } from "@/hooks/use-toast"
import { Progress } from "@/components/ui/progress"

interface FileSplitterProps {
  onSplitComplete: (files: File[]) => void
}

const FileSplitter: React.FC<FileSplitterProps> = ({ onSplitComplete }) => {
  const [file, setFile] = useState<File | null>(null)
  const [parts, setParts] = useState<number | null>(null)
  const [splitFiles, setSplitFiles] = useState<File[]>([])
  const [splitting, setSplitting] = useState<boolean>(false)
  const [progress, setProgress] = useState<number>(0)
  const [error, setError] = useState<string | null>(null)
  const { toast } = useToast()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    setFile(selectedFile || null)
    setSplitFiles([]) // Reset split files when a new file is selected
  }

  const calculateOptimalParts = useCallback(() => {
    if (!file) return 5 // Default value

    const fileSizeInMB = file.size / (1024 * 1024)
    let optimalParts = 5 // Default value

    if (fileSizeInMB > 100) {
      optimalParts = 20
    } else if (fileSizeInMB > 50) {
      optimalParts = 15
    } else if (fileSizeInMB > 10) {
      optimalParts = 10
    }

    return optimalParts
  }, [file])

  // Remplacer la fonction splitFileSimple par cette version améliorée
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

        // Calculer les positions de début et fin pour le contenu (sans l'en-tête)
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

  const handleSplitFile = () => {
    if (!file) {
      toast({
        title: "Erreur",
        description: "Veuillez sélectionner un fichier.",
        variant: "destructive",
      })
      return
    }

    splitFileSimple()
  }

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Diviseur de fichier</h1>
      <div className="mb-4">
        <Label htmlFor="file">Sélectionner un fichier</Label>
        <Input type="file" id="file" onChange={handleFileChange} />
      </div>

      {file && (
        <div className="mb-4">
          <Label htmlFor="parts">Nombre de parties (optionnel)</Label>
          <Slider
            id="parts"
            defaultValue={[calculateOptimalParts()]}
            max={20}
            min={2}
            step={1}
            onValueChange={(value) => setParts(value[0])}
          />
          <p className="text-sm text-muted-foreground">{parts || calculateOptimalParts()} parties</p>
        </div>
      )}

      <Button onClick={handleSplitFile} disabled={splitting}>
        {splitting ? "Division en cours..." : "Diviser le fichier"}
      </Button>

      {splitting && <Progress value={progress} className="mt-4" />}

      {error && <div className="text-red-500 mt-4">Erreur: {error}</div>}

      {splitFiles.length > 0 && (
        <div className="mt-4">
          <h2 className="text-lg font-semibold mb-2">Fichiers divisés:</h2>
          <ul>
            {splitFiles.map((splitFile, index) => (
              <li key={index}>
                {splitFile.name} ({splitFile.size} bytes)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default FileSplitter
