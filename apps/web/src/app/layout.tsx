import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Geist_Mono } from "next/font/google";
import "./globals.css";

import { ThemeProvider } from "@/components/layout/theme-provider";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AppSidebar } from "@/components/layout/app-sidebar";
import { Header } from "@/components/layout/header";
import { Toaster } from "@/components/ui/sonner";
import { ChatProvider } from "@/lib/chat-context";
import { RefreshProvider } from "@/lib/refresh-context";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Agentic RAG Starter Kit",
  description: "Chat with your documents — powered by LanceDB, LangChain, and Backblaze B2",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${geistMono.variable} antialiased`}
      >
        <ThemeProvider>
          <ChatProvider>
          <RefreshProvider>
            <SidebarProvider>
              <TooltipProvider>
                <AppSidebar />
                <div className="flex flex-1 flex-col">
                  <Header />
                  <main className="flex-1 overflow-auto p-6">{children}</main>
                </div>
                <Toaster />
              </TooltipProvider>
            </SidebarProvider>
          </RefreshProvider>
          </ChatProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
