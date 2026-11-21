import "./globals.css";

export const metadata = {
  title: "Console Interoperabilitas FHIR | OpenMRS, OpenEMR, SATUSEHAT",
  description:
    "Pemantauan sinkronisasi HL7 FHIR R4 antara OpenMRS, OpenEMR, dan SATUSEHAT: status konektivitas, antrean pekerjaan, konflik data, dan pemetaan identitas.",
};

export const viewport = {
  themeColor: "#257e7b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
