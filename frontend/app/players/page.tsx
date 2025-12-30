export default function PlayersPage() {
  return (
    <div className="min-h-screen">
      <header className="bg-gray-900 text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-3xl font-bold">Players</h1>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="mb-6">
          <input
            type="text"
            placeholder="Search players..."
            className="w-full max-w-md px-4 py-2 border rounded-lg"
          />
        </div>

        <div className="text-gray-600">
          <p>Player list will be populated from API...</p>
        </div>
      </main>
    </div>
  );
}
