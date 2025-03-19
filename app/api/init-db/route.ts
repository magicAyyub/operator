import { NextResponse } from "next/server"
import { initializeDatabase } from "@/lib/db"

export async function GET() {
  try {
    const result = await initializeDatabase()
    return NextResponse.json(result)
  } catch (error) {
    console.error("Erreur lors de l'initialisation de la base de données:", error)
    return NextResponse.json({ error: "Erreur lors de l'initialisation de la base de données" }, { status: 500 })
  }
}

