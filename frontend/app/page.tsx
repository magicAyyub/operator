import { Suspense } from "react"
import { DataTable } from "@/components/data-table"
import { DataFilter } from "@/components/data-filter"
import { DataStats } from "@/components/data-stats"
import { Skeleton } from "@/components/ui/skeleton"
import { ActionBar } from "@/components/action-bar"

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col">
      <div className="bg-gradient-to-b from-zinc-900 to-zinc-800 text-white">
        <div className="container mx-auto py-8">
          <h1 className="text-3xl font-bold tracking-tight mb-2">Tableau de Bord Opérateur</h1>
          <p className="text-zinc-300">Analysez et filtrez les données des opérateurs</p>
        </div>
      </div>

      <ActionBar />

      <div className="container mx-auto py-8 space-y-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Suspense fallback={<Skeleton className="h-[180px] w-full" />}>
            <DataStats type="operators" />
          </Suspense>
          <Suspense fallback={<Skeleton className="h-[180px] w-full" />}>
            <DataStats type="status" />
          </Suspense>
          <Suspense fallback={<Skeleton className="h-[180px] w-full" />}>
            <DataStats type="2fa" />
          </Suspense>
        </div>

        <div className="bg-white rounded-xl shadow-sm border p-6">
          <DataFilter />
          <Suspense fallback={<div className="h-96 flex items-center justify-center">Chargement des données...</div>}>
            <DataTable />
          </Suspense>
        </div>
      </div>
    </main>
  )
}

