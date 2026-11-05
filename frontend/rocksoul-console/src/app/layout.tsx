import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ROCKSOUL — Control Plane",
  description: "Provider intelligence, execution traces, routing and Arena evidence.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
