import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Legal Document AI Assistant",
  description: "Document understanding and grounded drafting workflow",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
