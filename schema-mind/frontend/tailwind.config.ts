const { fontFamily } = require('tailwindcss/defaultTheme')

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'sm-bg': '#000000',
        'sm-text': '#ffffff',
        'sm-muted': '#8e8e8e',
        'sm-nav-text': '#2e2e2e',
        'sm-pill': '#28282a',
        'sm-sign-in': '#c8c8c8',
        'sm-trust-bg': '#28282a',
        'sm-trust-border': 'rgba(255, 255, 255, 0.4)',
        'sm-trust-text': '#c4c2c3',
      },
      fontFamily: {
        sans: ['"Inter"', '"Segoe UI"', 'system-ui', 'sans-serif'],
        display: ['"BubbledotICG-FinePos"', '"Geist Pixel Circle"', 'monospace'],
      },
      keyframes: {
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-18px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        reveal: {
          '0%': { opacity: '0', transform: 'translateY(22px) scale(0.98)', filter: 'blur(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)', filter: 'blur(0)' },
        },
        headlineFade: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        revealPulse: {
          '0%': { opacity: '0', transform: 'translateY(22px) scale(0.98)', filter: 'blur(6px)' },
          '60%': { transform: 'translateY(-2px) scale(1.02)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)', filter: 'blur(0)' },
        },
        overlayIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        menuIn: {
          '0%': { opacity: '0', transform: 'translateY(-10px) scale(0.96)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        linkIn: {
          '0%': { opacity: '0', transform: 'translateX(-8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      animation: {
        'slideDown': 'slideDown 0.7s cubic-bezier(0.22, 1, 0.36, 1) both',
        'reveal': 'reveal 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'headlineFade': 'headlineFade 0.85s cubic-bezier(0.22, 1, 0.36, 1) both',
        'revealPulse': 'revealPulse 0.85s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'overlayIn': 'overlayIn 0.28s ease-out both',
        'menuIn': 'menuIn 0.38s cubic-bezier(0.22, 1, 0.36, 1) both',
        'linkIn': 'linkIn 0.4s ease-out both',
      },
    },
  },
  plugins: [],
}