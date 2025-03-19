import { NextResponse } from "next/server"
import { importData } from "@/lib/import"

export async function POST(request) {
  try {
    const formData = await request.formData()
    const result = await importData(formData)

    return NextResponse.json(result)
  } catch (error) {
    console.error("Erreur lors de l'importation:", error)
    return NextResponse.json({ error: "Erreur lors de l'importation" }, { status: 500 })
  }
}

