"use client"

import { ImportDialog } from "@/components/import-dialog"

export function ActionBar() {
  return (
    <div className="bg-white border-b sticky top-0 z-10 shadow-sm">
      <div className="container mx-auto py-3 flex items-center justify-between">
        <ImportDialog />
      </div>
    </div>
  )
}

