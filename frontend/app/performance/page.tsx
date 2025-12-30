export default function PerformancePage() {
  return (
    <div className="min-h-screen">
      <header className="bg-gray-900 text-white py-6">
        <div className="container mx-auto px-4">
          <h1 className="text-3xl font-bold">Past Performance</h1>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <div className="grid md:grid-cols-3 gap-6 mb-8">
          <div className="border rounded-lg p-6">
            <p className="text-sm text-gray-600 mb-2">Win Rate</p>
            <p className="text-3xl font-bold">--</p>
          </div>
          <div className="border rounded-lg p-6">
            <p className="text-sm text-gray-600 mb-2">Net Balance</p>
            <p className="text-3xl font-bold">$--</p>
          </div>
          <div className="border rounded-lg p-6">
            <p className="text-sm text-gray-600 mb-2">Picks Tracked</p>
            <p className="text-3xl font-bold">--</p>
          </div>
        </div>

        <div className="text-gray-600">
          <p>Performance data will be populated from API...</p>
        </div>
      </main>
    </div>
  );
}
