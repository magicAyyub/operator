"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { CalendarIcon, FilterX, Filter } from "lucide-react"
import { format } from "date-fns"
import { fr } from "date-fns/locale"
import { getFilterOptions } from "@/lib/data"

export function DataFilter() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [options, setOptions] = useState({
    statuts: [],
    fa_statuts: [],
    annees: [],
  })

  const [filters, setFilters] = useState({
    statut: searchParams.get("statut") || "",
    fa_statut: searchParams.get("fa_statut") || "",
    limite_type: searchParams.get("limite_type") || "",
    limite_valeur: searchParams.get("limite_valeur") || "",
    date_min: searchParams.get("date_min") || "",
    date_max: searchParams.get("date_max") || "",
    annee: searchParams.get("annee") || "",
  })

  useEffect(() => {
    const loadOptions = async () => {
      try {
        const data = await getFilterOptions()
        setOptions(data)
      } catch (error) {
        console.error("Erreur lors du chargement des options:", error)
      }
    }

    loadOptions()
  }, [])

  const handleChange = (name, value) => {
    setFilters((prev) => ({ ...prev, [name]: value }))
  }

  const applyFilters = () => {
    const params = new URLSearchParams()

    Object.entries(filters).forEach(([key, value]) => {
      if (value) {
        params.set(key, value)
      }
    })

    router.push(`/?${params.toString()}`)
  }

  const resetFilters = () => {
    setFilters({
      statut: "",
      fa_statut: "",
      limite_type: "",
      limite_valeur: "",
      date_min: "",
      date_max: "",
      annee: "",
    })

    router.push("/")
  }

  return (
    <div className="space-y-4 mb-6">
      <div className="flex justify-between items-center">
        <h2 className="text-xl font-semibold">Filtres</h2>
        <Button variant="ghost" onClick={resetFilters} className="flex items-center gap-2 text-muted-foreground">
          <FilterX className="h-4 w-4" />
          Réinitialiser
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Statut</label>
          <Select value={filters.statut} onValueChange={(value) => handleChange("statut", value)}>
            <SelectTrigger>
              <SelectValue placeholder="Tous les statuts" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les statuts</SelectItem>
              {options.statuts.map((statut) => (
                <SelectItem key={statut} value={statut}>
                  {statut}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">2FA Statut</label>
          <Select value={filters.fa_statut} onValueChange={(value) => handleChange("fa_statut", value)}>
            <SelectTrigger>
              <SelectValue placeholder="Tous les statuts 2FA" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous les statuts 2FA</SelectItem>
              {options.fa_statuts.map((statut) => (
                <SelectItem key={statut} value={statut}>
                  {statut}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Limite %</label>
          <div className="flex space-x-2">
            <Select value={filters.limite_type} onValueChange={(value) => handleChange("limite_type", value)}>
              <SelectTrigger className="w-24">
                <SelectValue placeholder="Op." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Aucun</SelectItem>
                <SelectItem value="lt">&lt;</SelectItem>
                <SelectItem value="gt">&gt;</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="number"
              placeholder="Valeur %"
              value={filters.limite_valeur}
              onChange={(e) => handleChange("limite_valeur", e.target.value)}
              min="0"
              max="100"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Année</label>
          <Select value={filters.annee} onValueChange={(value) => handleChange("annee", value)}>
            <SelectTrigger>
              <SelectValue placeholder="Toutes les années" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les années</SelectItem>
              {options.annees.map((annee) => (
                <SelectItem key={annee} value={annee}>
                  {annee}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Date minimum</label>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="w-full justify-start text-left font-normal">
                <CalendarIcon className="mr-2 h-4 w-4" />
                {filters.date_min ? (
                  format(new Date(filters.date_min), "PPP", { locale: fr })
                ) : (
                  <span>Sélectionner une date</span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={filters.date_min ? new Date(filters.date_min) : undefined}
                onSelect={(date) => handleChange("date_min", date ? format(date, "yyyy-MM-dd") : "")}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Date maximum</label>
          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" className="w-full justify-start text-left font-normal">
                <CalendarIcon className="mr-2 h-4 w-4" />
                {filters.date_max ? (
                  format(new Date(filters.date_max), "PPP", { locale: fr })
                ) : (
                  <span>Sélectionner une date</span>
                )}
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-auto p-0">
              <Calendar
                mode="single"
                selected={filters.date_max ? new Date(filters.date_max) : undefined}
                onSelect={(date) => handleChange("date_max", date ? format(date, "yyyy-MM-dd") : "")}
                initialFocus
              />
            </PopoverContent>
          </Popover>
        </div>
      </div>

      <Button onClick={applyFilters} className="mt-4 flex items-center gap-2">
        <Filter className="h-4 w-4" />
        Appliquer les filtres
      </Button>
    </div>
  )
}

