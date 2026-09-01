import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SchemaMind — Intelligence Designed To Evolve",
  description:
    "Transform any text into personalized memory patterns. AI-powered learning that adapts to how your brain works.",
  openGraph: {
    title: "SchemaMind — Intelligence Designed To Evolve",
    description:
      "Transform any text into personalized memory patterns. AI-powered learning that adapts to how your brain works.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* Font Awesome 6.5.2 */}
        <link
          rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css"
          integrity="sha512-SnH5WK+bZxgPHs44uWIX+LLJAJ9/2PkPKZ5QiAj6Ta86w+fsb2TkcmfRyVX3pBnMFcV7oQPJkl9QevSCWr3W6A=="
          crossOrigin="anonymous"
          referrerPolicy="no-referrer"
        />
      </head>
      <body>
        {/* Fixed Video Background */}
        <video className="bg-video" autoPlay muted loop playsInline>
          <source
            src="https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260809_012548_ef22562c-c0ae-4816-ad9d-f8922af4e6a7.mp4"
            type="video/mp4"
          />
        </video>
        <div className="bg-overlay" />

        {/* Page Content */}
        <div className="content">{children}</div>
      </body>
    </html>
  );
}