'use client'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { clearToken, isLoggedIn } from '@/lib/auth'

export default function Nav() {
  const router = useRouter()
  const pathname = usePathname()
  const [loggedIn, setLoggedIn] = useState(false)

  useEffect(() => {
    setLoggedIn(isLoggedIn())
  }, [pathname])

  const logout = () => {
    clearToken()
    setLoggedIn(false)
    router.push('/login')
  }

  return (
    <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
      <Link href="/" className="text-white font-bold text-lg tracking-tight">
        SynthRare
      </Link>
      <div className="flex items-center gap-6">
        <Link href="/catalog" className="text-gray-400 hover:text-white text-sm transition-colors">
          Catalog
        </Link>
        {loggedIn ? (
          <>
            <Link href="/dashboard" className="text-gray-400 hover:text-white text-sm transition-colors">
              Dashboard
            </Link>
            <button
              onClick={logout}
              className="text-gray-400 hover:text-white text-sm transition-colors"
            >
              Logout
            </button>
          </>
        ) : (
          <>
            <Link href="/login" className="text-gray-400 hover:text-white text-sm transition-colors">
              Login
            </Link>
            <Link
              href="/register"
              className="px-4 py-1.5 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Sign up
            </Link>
          </>
        )}
      </div>
    </nav>
  )
}
