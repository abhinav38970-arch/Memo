"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

/* ── Stat counters ── */
const stats = [
  { icon: "<", target: 120, suffix: "ms", decimals: 0, label: "Inference Time" },
  { icon: "%", target: 99.99, suffix: "%", decimals: 2, label: "Platform Uptime" },
  { icon: "*", target: 24, suffix: "/7", decimals: 0, label: "Autonomous Runtime" },
  { icon: "#", target: 2.4, suffix: "M", decimals: 1, label: "Context Windows" },
];

/* ── Count-up hook ── */
function useCountUp(target: number, decimals: number, duration: number, delay: number) {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const counted = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !counted.current) {
          counted.current = true;
          setTimeout(() => {
            const startTime = performance.now();
            function tick(now: number) {
              const elapsed = now - startTime;
              const progress = Math.min(elapsed / duration, 1);
              const eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
              setValue(eased * target);
              if (progress < 1) {
                requestAnimationFrame(tick);
              } else {
                setValue(target);
              }
            }
            requestAnimationFrame(tick);
          }, delay);
        }
      },
      { threshold: 0.25 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [target, duration, delay]);

  return { value, ref };
}

function StatCard(props: {
  icon: string;
  target: number;
  suffix: string;
  decimals: number;
  label: string;
  delay: number;
}) {
  const { value, ref } = useCountUp(props.target, props.decimals, 1500 + props.delay * 80, 480 + props.delay * 90);

  return (
    <div
      className="flex flex-col items-center gap-1 stat anim"
      style={{ animationDelay: `${0.5 + props.delay * 0.08}s` }}
    >
      <span className="stat-icon text-white">{props.icon}</span>
      <span ref={ref} className="stat-value text-white text-[clamp(18px,2.2vw,26px)]">
        {value.toFixed(props.decimals)}
        <span>{props.suffix}</span>
      </span>
      <span className="text-[#8e8e8e] text-[clamp(11px,1.2vw,12.5px)]">{props.label}</span>
    </div>
  );
}

const features = [
  {
    icon: "fa-brain",
    title: "Personalized Patterns",
    description: "Tell us how YOUR memory works — acronyms, analogies, stories, movies, sports, anything. We generate patterns tailored to you.",
  },
  {
    icon: "fa-rotate",
    title: "Adaptive Quizzing",
    description: "If a pattern isn't sticking, we switch. Our AI detects what isn't working and tries a different approach.",
  },
  {
    icon: "fa-paste",
    title: "Paste Any Material",
    description: "Textbook paragraphs, code documentation, lecture notes, video transcripts — paste anything and watch it transform.",
  },
  {
    icon: "fa-chart-line",
    title: "Track Your Progress",
    description: "See which patterns work best for you over time. Your brain has a learning style — we help you find it.",
  },
  {
    icon: "fa-sliders",
    title: "Custom Anything",
    description: "Remember things through The Matrix? Football plays? Your favorite TV show? Just describe it — we make it work.",
  },
  {
    icon: "fa-gauge-high",
    title: "Built for Speed",
    description: "Powered by Groq's ultra-fast inference. Patterns generate in seconds, not minutes. Study more, wait less.",
  },
];

export default function HomePage() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileMenuVisible, setMobileMenuVisible] = useState(false);

  useEffect(() => {
    function handleEsc(e: KeyboardEvent) {
      if (e.key === "Escape") closeMenu();
    }
    function handleResize() {
      if (window.innerWidth > 720) closeMenu();
    }
    if (menuOpen) {
      document.addEventListener("keydown", handleEsc);
      window.addEventListener("resize", handleResize);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleEsc);
      window.removeEventListener("resize", handleResize);
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  function openMenu() {
    setMenuOpen(true);
    setTimeout(() => setMobileMenuVisible(true), 10);
  }

  function closeMenu() {
    setMobileMenuVisible(false);
    setTimeout(() => setMenuOpen(false), 300);
  }

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
          }
        });
      },
      { threshold: 0.15 }
    );

    document.querySelectorAll(".anim").forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <main className="relative">
      {/* ── HERO SECTION ── */}
      <section className="flex flex-col min-h-screen px-[clamp(14px,3vw,32px)] py-[clamp(16px,2.4vh,28px)]">
        {/* Header */}
        <header
          className="flex items-center justify-between w-full max-w-[720px] mx-auto gap-[clamp(18px,2.8vw,28px)] header-anim"
          style={{ flexShrink: 0 }}
        >
          <Link
            href="/"
            className="w-[clamp(40px,4.4vw,46px)] h-[clamp(40px,4.4vw,46px)] rounded-full bg-white shadow-[0_4px_14px_rgba(0,0,0,0.16)] flex items-center justify-center hover:scale-105 transition-transform flex-shrink-0"
          >
            <svg width="72%" height="72%" viewBox="0 0 24 24" fill="none" xmlns="http://ww.w3.org/2000/svg">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#111" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center h-[clamp(44px,5.2vw,48px)] max-w-[430px] flex-1 bg-white roundd-ful px-2 py-1 shadow-[0_4px_14px_rgba(0,0,0,0.16)]">
            {["Home", "Product", "Case Studies", "Contact"].map((item, i) => (
              <a
                key={item}
                href={i === 0 ? "/" : "#"}
                className={`relative flex-1 text-center text-[clamp(13px,1.4vw,15px)] font-medium tracking-[-0.01em] text-[#2e2e2e] ${
                  i === 0 ? "opacity-100" : "opacity-50 hover:opacity-75"
                } transition-opacity`}
              >
                {item}
                {i === 0 && <span className="nav-active" />}
              </a>
            ))}
          </nav>

          <Link
            href="/pp"
            className="hidden md:flex items-center h-[clamp(44px,5.2vw,48px)] px-5 bg-[#28282a] text-[#c8c8c8] rounded-full shadow-[0_4px_14px_rgba(0,0,0,0.16)] hover:bg-[#323234] hover:text-white hover:-translate-y-0.5 transition-all text-[clamp(13px,1.4vw,15px)] font-medium"
          >
            Try SchemaMind
          </Link>

          {/* Mobile Burger */}
          <button
            className="md:hidden w-12 h-12 rounded-full bg-[#28282a] flex flex-col items-center justify-center gap-[5px] flex-shrink-0"
            onClick={menuOpen ? closeMenu : openMenu}
            aria-label="Menu"
          >
            <span className="burger-line" />
            <span className="burger-line" />
            <span className="burger-line" />
          </button>
        </header>

        {/* Mobile Menu Overlay */}
        {menuOpen && (
          <div className="md:hidden mobile-overlay" onClick={closeMenu}>
            <div
              className="mobile-sheet"
              onClick={(e) => e.stopPropagation()}
              style={{ opacity: mobileMenuVisible ? 1 : 0 }}
            >
              <div className="flex flex-col gap-3">
                {["Home", "Product", "Case Studies", "Contact"].map((item, i) => (
                  <a
                    key={item}
                    href={i === 0 ? "/" : "#"}
                    className={`relative py-2 px-4 text-[#2e2e2e] text-lg font-medium ${
                      i === 0 ? "opacity-100" : "opacity-60"
                    }`}
                    style={{ animation: mobileMenuVisible ? `linkIn 0.4s ease-out ${0.1 + i * 0.08}s both` : "none" }}
                    onClick={closeMenu}
                  >
                    {item}
                    {i === 0 && (
                      <span
                        style={{
                          position: "absolute",
                          bottom: "8px",
                          left: "50%",
                          transform: "translateX(-50%)",
                          width: "3px",
                          height: "3px",
                          background: "#000",
                          borderRadius: "50%",
                          boxShadow: "-5px 0 0 #000, 5px 0 0 #000",
                        }}
                      />
                    )}
                  </a>
                ))}
                <Link
                  href="/pp"
                  className="mt-3 w-full text-center py-3 bg-[#28282a] text-white rounded-full font-medium"
                  onClick={closeMenu}
                >
                  Try SchemaMind
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* ── Hero Center ── */}
        <div className="flex-1 flex flex-col items-center justify-center text-center gap-4">
          {/* Trust Row */}
          <div
            className="inline-flex items-center mb-[clamp(16px,2.5vh,26px)] anim"
            style={{
              "--trust-size": "clamp(36px, 4.5vw, 42px)",
              animationDelay: "0.05s",
            } as React.CSSProperties}
          >
            <div className="trust-avatar relative" style={{ zIndex: 1 }}>
              <div className="trust-avatar-inner">
                <i className="fa-brands fa-microsoft" />
              </div>
            </div>
            <div
              className="trust-avatar relative"
              style={{ marginLeft: "calc(var(--trust-size) * -0.42)", zIndex: 2 }}
            >
              <div className="trust-avatar-inner">
                <i className="fa-brands fa-amazon" />
              </div>
            </div>
            <div
              className="trust-avatar relative"
              style={{ marginLeft: "calc(var(--trust-size) * -0.42)", zIndex: 4 }}
            >
              <div className="trust-avatar-inner">
                <i className="fa-brands fa-google" />
              </div>
            </div>
            <div
              className="h-[var(--trust-size)] bg-[#28282a] border border-[rgba(255,255,255,0.4)] rounded-full flex items-center"
              style={{
                marginLeft: "calc(var(--trust-size) * -0.42)",
                paddingLeft: "calc(var(--trust-size) * 0.58)",
                paddingRight: "clamp(14px, 2.5vw, 22px)",
              }}
            >
              <span className="text-[#c4c2c3] font-medium whitespace-nowrap text-[clamp(12px,1.4vw,13.5px)]">
                Trusted by 2000+ Enterprises
              </span>
            </div>
          </div>

          {/* Headline */}
          <div className="headline">
            <span className="headline-line">Intelligence</span>
            <span className="headline-line">Designed To Evolve</span>
          </div>

          {/* Subhead */}
          <p
            className="text-[#d0d0d0] opacity-80 font-normal leading-relaxed max-w-[min(500px,92%)] anim"
            style={{
              fontSize: "clamp(calc(13.5px + 2pt), calc(1.55vw + 2pt), calc(16.5px + 2pt))",
              animationDelay: "0.28s",
            }}
          >
            Build applications that reason, adapt and collaborate using a modular
            AI platform designed for production.
          </p>

          {/* CTA */}
          <Link
            href="/pp"
            className="inline-block bg-white text-black font-semibold rounded-full cta-glow hover:-translate-y-0.5 hover:scale-102 transition-all anim"
            style={{
              padding: "clamp(11px, 1.6vh, 13px) clamp(22px, 3vw, 28px)",
              fontSize: "clamp(13.5px, 1.5vw, 14.5px)",
              animation: "revealPulse 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards",
              animationDelay: "0.4s",
            }}
          >
            Get Started
          </Link>
        </div>

        {/* ── Stats Footer ── */}
        <div className="stats-grid mx-auto w-full mt-8 pb-4 flex-shrink-0">
          {stats.map((stat, i) => (
            <StatCard key={stat.label} {...stat} delay={i} />
          ))}
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="section-dark py-20 px-4 md:px-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16 anim">
            <h2 className="headline text-4xl md:text-5xl mb-4">
              <span className="headline-line block" style={{ animationDelay: "0.1s" }}>
                How SchemaMind Works
              </span>
            </h2>
            <p className="text-[#d0d0d0] opacity-80 text-lg max-w-2xl mx-auto anim" style={{ animationDelay: "0.2s" }}>
              Three steps from confusion to mastery. Your way.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 mb-20">
            {[
              { num: "01", title: "Paste Your Material", desc: "Any text — textbook, notes, docs, transcripts. Paste it in and we analyze the structure." },
              { num: "02", title: "AI Generates Your Patterns", desc: "Acronyms, analogies, stories, or YOUR custom method. Patterns built for how YOU remember." },
              { num: "03", title: "Quiz Until It Sticks", desc: "Cloze tests, MCQs, and adaptive retries. If it's not working, we switch strategies automatically." },
            ].map((step, i) => (
              <div
                key={step.num}
                className="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-white/10 anim"
                style={{ animationDelay: `${0.3 + i * 0.15}s` }}
              >
                <span className="stat-icon text-3xl text-white/40">{step.num}</span>
                <h3 className="text-xl font-semibold mt-3 mb-2">{step.title}</h3>
                <p className="text-[#d0d0d0] opacity-80 text-sm leading-relaxed">{step.desc}</p>
              </div>
            ))}
          </div>

          {/* Features Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, i) => (
              <div
                key={feature.title}
                className="bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all anim"
                style={{ animationDelay: `${0.4 + i * 0.1}s` }}
              >
                <i className={`fa-solid ${feature.icon} text-2xl mb-4 text-white/60`} />
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-[#d0d0d0] opacity-80 text-sm leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="py-20 px-4 text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="headline text-3xl md:text-5xl mb-4 anim" style={{ animationDelay: "0.1s" }}>
            <span className="headline-line block" style={{ fontSize: "clamp(24px, 5vw, 56px)" }}>
              Ready to Learn Faster?
            </span>
          </h2>
          <p className="text-[#d0d0d0] opacity-80 text-lg mb-8 anim" style={{ animationDelay: "0.2s" }}>
            Stop re-reading. Start remembering. Try SchemaMind now.
          </p>
          <Link
            href="/pp"
            className="inline-block bg-white text-black font-semibold rounded-full cta-glow hover:-translate-y-0.5 hover:scale-102 transition-all px-10 py-4 text-lg anim"
            style={{ animationDelay: "0.3s" }}
          >
            Launch the Tool
          </Link>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="py-8 px-4 text-center border-t border-white/10">
        <p className="text-[#8e8e8e] text-sm">
          SchemaMind — Built for the Hackathon. AI-powered learning.
        </p>
      </footer>
    </main>
  );
}