import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getStats } from "@/lib/data"
import { Chart } from "./chart"

export async function DataStats({ type }) {
  const stats = await getStats(type)

  const getTitle = () => {
    switch (type) {
      case "operators":
        return "Top 5 Opérateurs"
      case "status":
        return "Répartition par Statut"
      case "2fa":
        return "Répartition par 2FA Statut"
      default:
        return "Statistiques"
    }
  }

  const getColor = () => {
    switch (type) {
      case "operators":
        return "#3b82f6"
      case "status":
        return "#10b981"
      case "2fa":
        return "#f59e0b"
      default:
        return "#6366f1"
    }
  }

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium">{getTitle()}</CardTitle>
      </CardHeader>
      <CardContent>
        <Chart data={stats} color={getColor()} />
      </CardContent>
    </Card>
  )
}

