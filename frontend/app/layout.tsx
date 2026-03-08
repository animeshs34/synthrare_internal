import type { Metadata } from 'next'
import './globals.css'
import Nav from '@/components/nav'

export const metadata: Metadata = {
  title: 'SynthRare — Synthetic Rare Data',
  description: 'Generate high-fidelity synthetic datasets for rare domains',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-white min-h-screen">
        <Nav />
        {children}
      </body>
    </html>
  )
}
