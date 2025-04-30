"use client"

import { useState, useEffect } from "react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

interface ServerStatusIndicatorProps {
  backendUrl?: string
}

export function ServerStatusIndicator({
  backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000",
}: ServerStatusIndicatorProps) {
  const [isOnline, setIsOnline] = useState<boolean | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  // Replace the checkServerStatus function with this improved version
  const checkServerStatus = async () => {
    try {
      const controller = new AbortController()
      const { signal } = controller

      // Create a promise that will resolve with the fetch result
      const fetchPromise = fetch(`${backendUrl}/api/health`, {
        method: "GET",
        signal,
      })

      // Create a timeout promise
      const timeoutPromise = new Promise((_, reject) => {
        const id = setTimeout(() => {
          controller.abort()
          reject(new Error("Timeout checking server status"))
        }, 5000)

        // Store the timeout ID so it can be cleared
        return () => clearTimeout(id)
      })

      // Race the fetch against the timeout
      const response = await Promise.race([fetchPromise, timeoutPromise])

      setIsOnline(response.ok)
    } catch (error) {
      // Handle abort errors gracefully
      if (error.name === "AbortError") {
        console.log("Server status check timed out")
      } else {
        console.error("Error checking server status:", error)
      }
      setIsOnline(false)
    } finally {
      setLastChecked(new Date())
    }
  }

  useEffect(() => {
    checkServerStatus()

    // Vérifier le statut toutes les 30 secondes
    const interval = setInterval(checkServerStatus, 30000)

    return () => clearInterval(interval)
  }, [backendUrl])

  if (isOnline === null) {
    return (
      <div className="flex items-center text-muted-foreground">
        <div className="h-2 w-2 rounded-full bg-gray-300 animate-pulse mr-2"></div>
        <span className="text-xs">Vérification...</span>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex items-center cursor-help">
            {isOnline ? (
              <>
                <div className="h-2 w-2 rounded-full bg-green-500 mr-2"></div>
                <span className="text-xs text-green-600">Serveur connecté</span>
              </>
            ) : (
              <>
                <div className="h-2 w-2 rounded-full bg-red-500 mr-2"></div>
                <span className="text-xs text-red-600">Serveur déconnecté</span>
              </>
            )}
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <div className="text-sm">
            <p className="font-medium">{isOnline ? "Serveur connecté" : "Serveur déconnecté"}</p>
            <p className="text-xs text-muted-foreground">
              Dernière vérification:{" "}
              {lastChecked
                ? new Intl.DateTimeFormat("fr-FR", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  }).format(lastChecked)
                : "Jamais"}
            </p>
            {!isOnline && (
              <p className="text-xs text-red-500 mt-1">
                Vérifiez que le serveur backend est en cours d'exécution sur {backendUrl}
              </p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
