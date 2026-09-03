"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

/* ── Realistic metric counters ── */
const stats = [
  { icon: "⚡", target: 2, suffix: "s", decimals: 1, label: "Pattern Generation" },
  { icon: "✓", target: 85, suffix: "%", decimals: 0, label: "Quiz Accuracy" },
  { icon: "🧠", target: 4, suffix: "", decimals: 0, label: "Learning Styles" },
  { icon: "♻️", target: 3, suffix: "", decimals: 0, label: "Adaptation Rounds" },
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
              const eased = 1 - Math.pow(1 - progress, 3);
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
      <span className="stat-icon text-white text-2xl">{props.icon}</span>
      <span ref={ref} className="stat-value text-white text-[clamp(18px,2.2vw,26px)]">
        {value.toFixed(props.decimals)}
        <span>{props.suffix}</span>
      </span>
      <span className="text-[#b4b4b4] text-[clamp(11px,1.2vw,12.5px)] text-on-video">{props.label}</span>
    </div>
  );
}

const features = [
  {
    icon: "fa-brain",
    title: "Personalized Learning Patterns",
    description: "Generate memory techniques tailored to your unique learning style—mnemonics, stories, analogies, or custom methods.",
  },
  {
    icon: "fa-rotate-right",
    title: "Adaptive Quizzing",
    description: "AI detects which patterns work best for you and adapts in real-time. Weak areas trigger different strategies.",
  },
  {
    icon: "fa-paste",
    title: "Paste Any Material",
    description: "Upload textbook paragraphs, documentation, lecture notes, or transcripts. Transform them instantly into study patterns.",
  },
  {
    icon: "fa-chart-line",
    title: "Track Progress",
    description: "Monitor which learning styles work best for you. Build your perfect learning profile over time.",
  },
  {
    icon: "fa-sliders",
    title: "Custom Memory Frameworks",
    description: "Not finding the right style? Describe your own memory system and we'll use it to create patterns.",
  },
  {
    icon: "fa-bolt",
    title: "Fast & Efficient",
    description: "Powered by Groq's fast inference. Generate patterns in seconds. Study more, wait less.",
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
            className="w-[clamp(40px,4.4vw,46px)] h-[clamp(40px,4.4vw,46px)] rounded-full bg-white shadow-[0_4px_14px_rgba(0,0,0,0.16)] flex items-center justify-center hover:scale-105 transition-transform"
          >
            <svg width="72%" height="72%" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="#111" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center h-[clamp(44px,5.2vw,48px)] max-w-[430px] flex-1 bg-white rounded-full px-2 py-1 shadow-[0_4px_14px_rgba(0,0,0,0.16)]">
            {["Home"].map((item, i) => (
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
            className="hidden md:flex items-center h-[clamp(44px,5.2vw,48px)] px-5 bg-[#28282a] text-[#e2e2e2] rounded-full shadow-[0_4px_14px_rgba(0,0,0,0.16)] hover:bg-[#323234] hover:text-white transition-colors text-[clamp(13px,1.4vw,15px)] font-medium"
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
                {["Home"].map((item, i) => (
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
                  className="mt-3 w-full text-center py-3 bg-[#28282a] text-white rounded-full font-medium hover:bg-[#323234] transition-colors"
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
          {/* Headline */}
          <div className="headline">
            <span className="headline-line">Learn Smarter</span>
            <span className="headline-line">Not Harder</span>
          </div>

          {/* Subhead */}
          <p
            className="text-[#eaeaea] font-normal leading-relaxed max-w-[min(550px,92%)] text-on-video anim"
            style={{
              fontSize: "clamp(calc(13.5px + 2pt), calc(1.55vw + 2pt), calc(16.5px + 2pt))",
              animationDelay: "0.28s",
            }}
          >
            Paste any text. Get personalized memory patterns tailored to how your brain learns. 
            Quiz yourself, adapt, and remember better.
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
            Start Learning Now
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
            <p className="text-[#eaeaea] text-lg max-w-2xl mx-auto anim" style={{ animationDelay: "0.2s" }}>
              Three simple steps to master any material.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 mb-20">
            {[
              { num: "1", title: "Paste Your Material", desc: "Share any text—textbook excerpts, lecture notes, articles, documentation. We analyze and understand it instantly." },
              { num: "2", title: "AI Generates Patterns", desc: "Choose your learning style (or create a custom one) and watch SchemaMind generate personalized memory patterns in seconds." },
              { num: "3", title: "Quiz & Adapt", desc: "Take adaptive quizzes to test retention. If something isn't sticking, SchemaMind switches strategies automatically." },
            ].map((step, i) => (
              <div
                key={step.num}
                className="bg-white/5 backdrop-blur-sm rounded-2xl p-8 border border-white/10 anim"
                style={{ animationDelay: `${0.3 + i * 0.15}s` }}
              >
                <span className="stat-icon text-4xl text-white/70">{step.num}</span>
                <h3 className="text-xl font-semibold mt-3 mb-2">{step.title}</h3>
                <p className="text-[#eaeaea] text-sm leading-relaxed">{step.desc}</p>
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
                <i className={`fa-solid ${feature.icon} text-2xl mb-4 text-white/85`} />
                <h3 className="text-lg font-semibold mb-2">{feature.title}</h3>
                <p className="text-[#eaeaea] text-sm leading-relaxed">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why SchemaMind Wins ── */}
      <section className="py-20 px-4 md:px-8">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-12 anim">
            <h2 className="headline text-3xl md:text-5xl mb-4" style={{ animationDelay: "0.1s" }}>
              <span className="headline-line block">Why SchemaMind Stands Out</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-8">
            {[
              {
                title: "Personalization at Scale",
                desc: "Supports built-in learning styles plus unlimited custom frameworks. Your brain, your way.",
              },
              {
                title: "Closed-Loop Learning",
                desc: "Not just generating patterns. AI adapts based on what works, creating a continuous improvement cycle.",
              },
              {
                title: "Production-Ready Architecture",
                desc: "Full-stack (Next.js + FastAPI). Smart rate-limiting on free-tier LLM. Zero database needed.",
              },
              {
                title: "Real Learning Outcomes",
                desc: "Measurable improvement through adaptive quizzes. Track which patterns work best for you.",
              },
            ].map((item, i) => (
              <div
                key={item.title}
                className="bg-white/5 backdrop-blur-sm rounded-2xl p-6 border border-white/10 anim"
                style={{ animationDelay: `${0.2 + i * 0.1}s` }}
              >
                <h3 className="text-lg font-semibold mb-3">{item.title}</h3>
                <p className="text-[#eaeaea] text-sm leading-relaxed">{item.desc}</p>
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
              Ready to Learn Differently?
            </span>
          </h2>
          <p className="text-[#eaeaea] text-lg mb-8 text-on-video anim" style={{ animationDelay: "0.2s" }}>
            Stop cramming. Start remembering. Try SchemaMind free, right now.
          </p>
          <Link
            href="/pp"
            className="inline-block bg-white text-black font-semibold rounded-full cta-glow hover:-translate-y-0.5 hover:scale-102 transition-all px-10 py-4 text-lg anim"
            style={{ animationDelay: "0.3s" }}
          >
            Launch SchemaMind
          </Link>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="py-8 px-4 text-center border-t border-white/10">
        <p className="text-[#b4b4b4] text-sm">
          SchemaMind — AI-powered personalized learning. Built with care.
        </p>
      </footer>
    </main>
  );
}
