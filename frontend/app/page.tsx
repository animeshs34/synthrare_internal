export default function HomePage() {
  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gray-950 text-white">
      <h1 className="text-5xl font-bold mb-4">SynthRare</h1>
      <p className="text-xl text-gray-400 mb-8">
        Synthetic rare data generation platform
      </p>
      <div className="flex gap-4">
        <a
          href="/dashboard"
          className="px-6 py-3 bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Dashboard
        </a>
        <a
          href="/catalog"
          className="px-6 py-3 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
        >
          Catalog
        </a>
      </div>
    </main>
  );
}
