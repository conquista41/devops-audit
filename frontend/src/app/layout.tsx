import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HealthCheck.dev — DevOps Audit Tool",
  description: "Scan your GitHub repos, Kubernetes configs, and Dockerfiles for security issues.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
