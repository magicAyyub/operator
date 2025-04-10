"use client"

import { useState, useEffect } from "react"
import { ImportDialog } from "@/components/import-dialog"
import { NotificationsDropdown } from "@/components/notifications-dropdown"
import { checkFileExists } from "@/lib/data"

export function ActionBar() {
  const [fileExists, setFileExists] = useState(false)

  // Vérifier si un fichier existe déjà
  const checkFile = async () => {
    const exists = await checkFileExists()
    setFileExists(exists)
  }

  // Vérifier au chargement et après chaque action
  useEffect(() => {
    checkFile()
  }, [])

  return (
    <div className="bg-white border-b sticky top-0 z-10 shadow-sm">
      <div className="container mx-auto py-3 flex items-center justify-between">
        <div></div> {/* Espace vide pour l'alignement */}
        <div className="flex gap-2">
          <NotificationsDropdown />
          <ImportDialog fileExists={fileExists} />
        </div>
      </div>
    </div>
  )
}
