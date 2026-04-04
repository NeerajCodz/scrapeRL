/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Navy Blue and Cyan Theme
        navy: {
          50: '#e6f0ff',
          100: '#b3d4ff',
          200: '#80b8ff',
          300: '#4d9cff',
          400: '#1a80ff',
          500: '#0a2540',  // Base navy
          600: '#081f35',
          700: '#06192a',
          800: '#04131f',
          900: '#020d14',
          950: '#001f3f',  // Deep navy
        },
        cyan: {
          50: '#e6fffa',
          100: '#b3fff0',
          200: '#80ffe5',
          300: '#4dffda',
          400: '#1affd0',
          500: '#00d9ff',  // Bright cyan
          600: '#00b8d4',
          700: '#0097a9',
          800: '#00767e',
          900: '#005553',
          950: '#64ffda',  // Neon cyan
        },
        dark: {
          50: '#f7f8fa',
          100: '#e3e6eb',
          200: '#c7ced7',
          300: '#a3aeba',
          400: '#7e8e9e',
          500: '#5a6e82',
          600: '#445566',
          700: '#0a192f',  // Navy base
          800: '#0a1929',
          900: '#051120',
          950: '#020a14',
        },
        accent: {
          primary: '#00d9ff',     // Bright cyan
          secondary: '#64ffda',   // Neon cyan
          tertiary: '#0097a9',    // Deep cyan
          navy: '#0a192f',        // Navy
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'glow': 'glow 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        glow: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 20px rgba(0, 217, 255, 0.5)' },
          '50%': { opacity: '0.8', boxShadow: '0 0 30px rgba(100, 255, 218, 0.7)' },
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-navy': 'linear-gradient(135deg, #0a192f 0%, #051120 100%)',
        'gradient-cyan': 'linear-gradient(135deg, #00d9ff 0%, #64ffda 100%)',
      },
    },
  },
  plugins: [],
};
