import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { getStats } from "@/lib/data"
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts"

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
        <div className="h-[140px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stats}>
              <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis hide />
              <Tooltip
                formatter={(value) => [`${value}%`, "Pourcentage"]}
                contentStyle={{
                  backgroundColor: "white",
                  border: "1px solid #e2e8f0",
                  borderRadius: "6px",
                  boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1)",
                }}
              />
              <Bar dataKey="value" fill={getColor()} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

