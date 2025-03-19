import { NextResponse } from "next/server"
import { exportToCSV } from "@/lib/export"

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url)
    const queryString = searchParams.toString()

    const { content, fileName } = await exportToCSV(queryString)

    return new NextResponse(content, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": `attachment; filename="${fileName}"`,
      },
    })
  } catch (error) {
    console.error("Erreur lors de l'exportation:", error)
    return NextResponse.json({ error: "Erreur lors de l'exportation" }, { status: 500 })
  }
}

