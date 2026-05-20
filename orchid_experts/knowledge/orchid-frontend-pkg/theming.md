<!-- Source: derived from orchid-frontend/AGENTS.md, orchid-website/src/content/packages/orchid-frontend.mdx, and codebase analysis -->

# Theming

The frontend uses Tailwind CSS v4 with `@theme inline` for a fully customizable design system. Unlike Tailwind v3 (which uses `tailwind.config.js`), Tailwind v4 uses CSS-first configuration with the `@theme` directive.

## Tailwind v4 Configuration

Theming is done via CSS custom properties in `src/app/globals.css`:

```css
@import "tailwindcss";

@theme inline {
  --color-orchid-50: #f0f4ff;
  --color-orchid-100: #dbe4ff;
  --color-orchid-200: #bac8ff;
  --color-orchid-300: #91a7ff;
  --color-orchid-400: #748ffc;
  --color-orchid-500: #5c7cfa;
  --color-orchid-600: #4c6ef5;
  --color-orchid-700: #4263eb;
  --color-orchid-800: #3b5bdb;
  --color-orchid-900: #364fc7;

  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-xl: 1rem;
}
```

## Orchid Palette

The default palette uses indigo-blue tones:
- Light shades (50-200) — Backgrounds, hover states, subtle accents.
- Mid shades (300-500) — Primary buttons, links, active states.
- Dark shades (600-900) — Text on light backgrounds, headings, borders.

Semantic colors:
- Green — Success states, approved actions, completed Bloom runs.
- Red — Error states, rejected actions, failed Bloom runs.
- Amber — Warning states, pending approvals, running Bloom runs.

## Re-skinning

### Brand Colors

Override the orchid color palette with your brand colors:

```css
@theme inline {
  --color-orchid-50: #f3e8ff;   /* Your lightest shade */
  --color-orchid-100: #e9d5ff;
  --color-orchid-500: #a855f7;  /* Your primary brand color */
  --color-orchid-700: #7e22ce;  /* Your darker shade */
  --color-orchid-900: #581c87;  /* Your darkest shade */
}
```

All components that reference `bg-orchid-500`, `text-orchid-700`, etc. automatically update. No component code changes needed.

### Typography

Change the font family and scale:

```css
@theme inline {
  --font-sans: "Your Custom Font", system-ui, sans-serif;
  --font-mono: "Fira Code", monospace;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
}
```

### Border Radius

Adjust corner rounding globally:

```css
@theme inline {
  --radius-md: 1rem;     /* Very rounded */
  --radius-md: 0.125rem; /* Very sharp */
}
```

## Component Customization

Components use Tailwind utility classes that reference theme tokens:

```tsx
<button className="bg-orchid-500 hover:bg-orchid-700 text-white rounded-md">
  Send
</button>

<div className="font-sans text-lg text-orchid-900">
  Welcome to Orchid Chat
</div>
```

Re-skinning the theme tokens automatically re-styles every component. This means you can fork the frontend, update a few CSS variables, and have a fully branded chat interface.

## Dark Mode

Dark mode uses CSS media queries and the `dark:` variant:

```css
:root {
  --color-surface: #ffffff;
  --color-text: #1a1a2e;
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-surface: #1a1a2e;
    --color-text: #e2e8f0;
  }
}
```

Components reference these with regular Tailwind classes: `bg-surface`, `text-text`. The `dark:` variant handles overrides: `dark:bg-gray-900`, `dark:text-white`.

## Font Loading

The Inter font is loaded via `next/font/google`:

```tsx
import { Inter } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});
```

This provides automatic font optimization (subsetting, preloading) by Next.js.

## Best Practices

- Never hardcode color values in components — always reference theme tokens.
- Use semantic utility classes (`text-orchid-500`) rather than arbitrary values (`text-[#4263eb]`).
- Test dark mode when adding new components.
- Keep the palette limited to 10 shades — more shades create confusion.
- Document which tokens are used for which purpose in a style guide.
