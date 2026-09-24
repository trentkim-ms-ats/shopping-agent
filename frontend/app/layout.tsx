import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "Trailshop · Your next trail starts here", description: "An evidence-first outdoor shopping assistant. Synthetic demo." };
const themeScript = `(() => {
  const param = new URLSearchParams(window.location.search).get("scoutTheme");
  const theme = param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
})();`;
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head><body>{children}</body></html>;
}
