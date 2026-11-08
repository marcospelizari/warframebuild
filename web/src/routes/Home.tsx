import { useQuery } from "@tanstack/react-query";
import { getHealth } from "@/api/client";

export function Home() {
  const health = useQuery({ queryKey: ["health"], queryFn: getHealth });
  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-semibold">warframeBuild</h1>
      <p className="mt-2 text-sm text-neutral-600">Placeholder page. Builds arrive in later steps.</p>
      <footer className="mt-8 text-xs text-neutral-500">
        Version {health.data?.version ?? "…"}
      </footer>
    </main>
  );
}
