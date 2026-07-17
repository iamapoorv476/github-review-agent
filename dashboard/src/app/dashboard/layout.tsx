import { Sidebar } from "@/components/sidebar";

export default function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="grid min-h-screen grid-cols-[232px_1fr] max-md:grid-cols-1">
      <Sidebar />
      <main className="min-w-0">
        <div className="max-w-[1120px] px-9 pb-16 pt-7 max-md:px-4.5 max-md:pt-5">{children}</div>
      </main>
    </div>
  );
}
