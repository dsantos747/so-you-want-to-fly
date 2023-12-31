/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      backgroundImage: {
        'gradient-destination':
          'radial-gradient(farthest-side at 20% 95%,rgb(255,255,255,0.8),rgb(255,255,255,0.8) 20%,rgb(255,255,255,0.5) 60%,rgb(255,255,255,0.1) 80%, transparent 95%)',
      },
    },
    animation: {
      'spin-slow': 'spin 1.5s linear infinite',
      'pulse': 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
    },
  },
  plugins: [],
};
