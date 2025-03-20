"use client"

import { useState, useEffect } from "react"
import { useSearchParams } from "next/navigation"
import { getData } from "@/lib/data"

export function useData(page = 1) {
  const [data, setData] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [totalPages, setTotalPages] = useState(0)
  const searchParams = useSearchParams()

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true)

      try {
        const filters = {
          statut: searchParams.get("statut") || "",
          fa_statut: searchParams.get("fa_statut") || "",
          limite_type: searchParams.get("limite_type") || "",
          limite_valeur: searchParams.get("limite_valeur") || "",
          date_min: searchParams.get("date_min") || "",
          date_max: searchParams.get("date_max") || "",
          annee: searchParams.get("annee") || "",
        }

        const result = await getData(page, filters)
        setData(result.data)
        setTotalPages(result.totalPages)
      } catch (error) {
        console.error("Erreur lors du chargement des données:", error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchData()
  }, [page, searchParams])

  return { data, isLoading, totalPages }
}

