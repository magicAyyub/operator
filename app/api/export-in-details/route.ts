import { NextResponse } from "next/server"
import { exportDetailedInData } from "@/lib/export"

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url)
    const queryString = searchParams.toString()

    const { content, fileName } = await exportDetailedInData(queryString)

    return new NextResponse(content, {
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": `attachment; filename="${fileName}"`,
      },
    })
  } catch (error) {
    console.error("Erreur lors de l'exportation des détails IN:", error)
    return NextResponse.json({ error: "Erreur lors de l'exportation des détails IN" }, { status: 500 })
  }
}

