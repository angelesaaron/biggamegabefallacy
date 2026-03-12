export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-sr-bg">
      <header className="border-b border-sr-border px-6 py-4">
        <h1 className="text-white font-semibold text-lg">System Admin</h1>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}
