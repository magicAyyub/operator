export const mockSecurityData = [
  {
    id: 1,
    operateur: "Orange",
    nombre_in: 1250,
    pourcentage_in: 35.8,
    statut: "Actif",
    fa_statut: "Activé",
    date: new Date("2025-02-15"),
    id_lin: "LIN001",
  },
  {
    id: 2,
    operateur: "SFR",
    nombre_in: 980,
    pourcentage_in: 28.1,
    statut: "Actif",
    fa_statut: "Désactivé",
    date: new Date("2025-02-14"),
    id_lin: "LIN002",
  },
  {
    id: 3,
    operateur: "Bouygues",
    nombre_in: 750,
    pourcentage_in: 21.5,
    statut: "Inactif",
    fa_statut: "En attente",
    date: new Date("2025-02-13"),
    id_lin: "LIN003",
  },
  {
    id: 4,
    operateur: "Free",
    nombre_in: 510,
    pourcentage_in: 14.6,
    statut: "Actif",
    fa_statut: "Activé",
    date: new Date("2025-02-12"),
    id_lin: "LIN004",
  },
  {
    id: 5,
    operateur: "Orange",
    nombre_in: 320,
    pourcentage_in: 9.2,
    statut: "Suspendu",
    fa_statut: "Désactivé",
    date: new Date("2025-01-15"),
    id_lin: "LIN005",
  },
  {
    id: 6,
    operateur: "SFR",
    nombre_in: 280,
    pourcentage_in: 8.0,
    statut: "Actif",
    fa_statut: "Activé",
    date: new Date("2025-01-14"),
    id_lin: "LIN006",
  },
  {
    id: 7,
    operateur: "Bouygues",
    nombre_in: 210,
    pourcentage_in: 6.0,
    statut: "Inactif",
    fa_statut: "En attente",
    date: new Date("2025-01-13"),
    id_lin: "LIN007",
  },
  {
    id: 8,
    operateur: "Free",
    nombre_in: 180,
    pourcentage_in: 5.2,
    statut: "Actif",
    fa_statut: "Activé",
    date: new Date("2025-01-12"),
    id_lin: "LIN008",
  },
  {
    id: 9,
    operateur: "Orange",
    nombre_in: 150,
    pourcentage_in: 4.3,
    statut: "Suspendu",
    fa_statut: "Désactivé",
    date: new Date("2024-12-15"),
    id_lin: "LIN009",
  },
  {
    id: 10,
    operateur: "SFR",
    nombre_in: 120,
    pourcentage_in: 3.4,
    statut: "Actif",
    fa_statut: "Activé",
    date: new Date("2024-12-14"),
    id_lin: "LIN010",
  },
  {
    id: 11,
    operateur: "Bouygues",
    nombre_in: 100,
    pourcentage_in: 2.9,
    statut: "Inactif",
    fa_statut: "En attente",
    date: new Date("2024-12-13"),
    id_lin: "LIN011",
  },
  {
    id: 12,
    operateur: "Free",
    nombre_in: 90,
    pourcentage_in: 2.6,
    statut: "Actif",
    fa_statut: "Activé",
    date: new Date("2024-12-12"),
    id_lin: "LIN012",
  },
]

// Données détaillées simulées pour les IN
export const mockDetailedInData = [
  // Orange (LIN001)
  ...Array.from({ length: 20 }, (_, i) => ({
    id: i + 1,
    id_lin: "LIN001",
    numero_in: `IN${100000 + i}`,
    date_activation: new Date(2025, 1, 15 - (i % 5)),
    statut_detail: i % 3 === 0 ? "Actif" : i % 3 === 1 ? "En attente" : "Inactif",
    type_service: i % 2 === 0 ? "Voix" : "Data",
    region: ["Île-de-France", "PACA", "Bretagne", "Normandie", "Grand Est"][i % 5],
  })),

  // SFR (LIN002)
  ...Array.from({ length: 15 }, (_, i) => ({
    id: i + 21,
    id_lin: "LIN002",
    numero_in: `IN${200000 + i}`,
    date_activation: new Date(2025, 1, 14 - (i % 4)),
    statut_detail: i % 3 === 0 ? "Actif" : i % 3 === 1 ? "En attente" : "Inactif",
    type_service: i % 2 === 0 ? "Voix" : "Data",
    region: ["Île-de-France", "PACA", "Bretagne", "Normandie", "Grand Est"][i % 5],
  })),

  // Bouygues (LIN003)
  ...Array.from({ length: 12 }, (_, i) => ({
    id: i + 36,
    id_lin: "LIN003",
    numero_in: `IN${300000 + i}`,
    date_activation: new Date(2025, 1, 13 - (i % 3)),
    statut_detail: i % 3 === 0 ? "Actif" : i % 3 === 1 ? "En attente" : "Inactif",
    type_service: i % 2 === 0 ? "Voix" : "Data",
    region: ["Île-de-France", "PACA", "Bretagne", "Normandie", "Grand Est"][i % 5],
  })),
]

// Options de filtres simulées
export const mockFilterOptions = {
  statuts: ["Actif", "Inactif", "Suspendu"],
  fa_statuts: ["Activé", "Désactivé", "En attente"],
  annees: ["2024", "2025"],
}

// Statistiques simulées
export const mockStats = {
  operators: [
    { name: "Orange", value: 49.3 },
    { name: "SFR", value: 39.5 },
    { name: "Bouygues", value: 30.4 },
    { name: "Free", value: 22.4 },
    { name: "Autres", value: 8.4 },
  ],
  status: [
    { name: "Actif", value: 65.0 },
    { name: "Inactif", value: 25.0 },
    { name: "Suspendu", value: 10.0 },
  ],
  "2fa": [
    { name: "Activé", value: 55.0 },
    { name: "Désactivé", value: 30.0 },
    { name: "En attente", value: 15.0 },
  ],
}

