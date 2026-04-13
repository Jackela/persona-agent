# Persona Agent Design System

A design system for a local role-playing AI agent framework with dynamic persona switching, mood management, and linguistic style customization.

## Visual Theme & Atmosphere

- **Mood**: Intelligent, intimate, and cinematic. The UI should feel like stepping into a conversation with a conscious entity.
- **Density**: Comfortable. Generous whitespace with focused content areas. Not cramped.
- **Philosophy**: "The interface disappears, the persona remains." Every visual element should serve the feeling of presence and personality.

## Color Palette & Roles

### Backgrounds
- `--bg-primary`: `#0a0a0a` (Void black - main canvas)
- `--bg-secondary`: `#111111` (Elevated surfaces, cards)
- `--bg-tertiary`: `#1a1a1a` (Input fields, hover states)
- `--bg-glass`: `rgba(17, 17, 17, 0.8)` (Modal backdrops, glassmorphism)

### Text
- `--text-primary`: `#fafafa` (Primary content)
- `--text-secondary`: `#a3a3a3` (Descriptions, metadata)
- `--text-tertiary`: `#737373` (Disabled, timestamps)
- `--text-muted`: `#525252` (Borders, dividers)

### Accents
- `--accent-emerald`: `#10b981` (Primary accent - intelligence, active states)
- `--accent-emerald-glow`: `rgba(16, 185, 129, 0.3)` (Glow effects)
- `--accent-terracotta`: `#e07a5f` (Warm accent - emotion, human connection)
- `--accent-terracotta-glow`: `rgba(224, 122, 95, 0.3)` (Warm glow)
- `--accent-purple`: `#a78bfa` (Creative states, special personas)

### Semantic Colors
- `--success`: `#10b981`
- `--warning`: `#f59e0b`
- `--error`: `#ef4444`
- `--info`: `#3b82f6`

## Typography Rules

### Font Families
- **Display**: `Inter`, system-ui, sans-serif (Headings, brand moments)
- **Body**: `Inter`, system-ui, sans-serif (All body text)
- **Mono**: `JetBrains Mono`, `Fira Code`, monospace (Code snippets, technical metadata)

### Type Scale
| Element | Size | Weight | Line Height | Letter Spacing |
|---------|------|--------|-------------|----------------|
| Hero | 48px / 3rem | 700 | 1.1 | -0.02em |
| H1 | 36px / 2.25rem | 600 | 1.2 | -0.02em |
| H2 | 28px / 1.75rem | 600 | 1.3 | -0.01em |
| H3 | 20px / 1.25rem | 500 | 1.4 | 0 |
| Body | 16px / 1rem | 400 | 1.6 | 0 |
| Body Small | 14px / 0.875rem | 400 | 1.5 | 0 |
| Caption | 12px / 0.75rem | 500 | 1.4 | 0.01em |
| Mono | 14px / 0.875rem | 400 | 1.5 | 0 |

## Component Stylings

### Buttons
- **Primary**: `bg-emerald-500`, `text-black`, `font-medium`, `px-5 py-2.5`, `rounded-full`
  - Hover: `bg-emerald-400`, subtle glow shadow `0 0 20px rgba(16, 185, 129, 0.3)`
  - Active: scale(0.98)
- **Secondary**: `bg-bg-tertiary`, `text-primary`, `border border-white/10`, `px-5 py-2.5`, `rounded-full`
  - Hover: `bg-white/5`, border brightens to `white/20`
- **Ghost**: `text-secondary`, transparent bg
  - Hover: `text-primary`, `bg-white/5`, `rounded-lg`

### Cards
- Background: `--bg-secondary`
- Border: `1px solid rgba(255, 255, 255, 0.06)`
- Border Radius: `16px` (1rem)
- Padding: `24px`
- Shadow: none by default, subtle glow on hover for interactive cards
- Hover: border brightens to `rgba(255, 255, 255, 0.1)`

### Inputs
- Background: `--bg-tertiary`
- Border: `1px solid rgba(255, 255, 255, 0.08)`
- Border Radius: `12px` (0.75rem)
- Padding: `12px 16px`
- Focus: border color `--accent-emerald`, subtle inner glow
- Placeholder: `--text-tertiary`

### Navigation
- **Sidebar**: `280px` width, `--bg-secondary`, right border `1px solid rgba(255,255,255,0.06)`
- **Nav Item**: `rounded-lg`, `px-3 py-2`, `text-secondary`
  - Active: `bg-white/5`, `text-primary`, left border `2px solid --accent-emerald`
  - Hover: `bg-white/5`, `text-primary`

### Persona Cards (Special Component)
- Large avatar (64px) with mood-indicator ring
- Mood ring color changes based on state:
  - Joyful: `--accent-emerald`
  - Warm: `--accent-terracotta`
  - Creative: `--accent-purple`
  - Neutral: `--text-secondary`
- Card shows persona name, current mood badge, and brief description

### Mood Badge
- Small pill badge: `px-2 py-0.5`, `rounded-full`, `text-xs`, `font-medium`
- Background is accent color at 15% opacity, text is full accent color

## Layout Principles

### Spacing Scale
Base unit: `4px`
- `xs`: 4px
- `sm`: 8px
- `md`: 16px
- `lg`: 24px
- `xl`: 32px
- `2xl`: 48px
- `3xl`: 64px

### Grid
- Main content max-width: `1200px`
- Dashboard grid: `280px sidebar` + `1fr content`
- Card grids: responsive `1fr` to `repeat(auto-fill, minmax(320px, 1fr))`

### Page Structure
```
[Sidebar | Main Content Area]
          [Header with title + actions]
          [Content sections in cards]
```

## Depth & Elevation

- No hard drop shadows. Use subtle borders and glows instead.
- **Glow 1 (subtle)**: `0 0 20px rgba(16, 185, 129, 0.1)` - for hovered interactive elements
- **Glow 2 (medium)**: `0 0 40px rgba(16, 185, 129, 0.15)` - for primary CTAs, active personas
- **Glow 3 (warm)**: `0 0 30px rgba(224, 122, 95, 0.2)` - for emotional moments, warm personas

## Motion & Interaction

- **Transitions**: `200ms cubic-bezier(0.4, 0, 0.2, 1)` for most UI elements
- **Page transitions**: Fade in `300ms ease-out`
- **Card hover**: translateY(-2px) + border brighten
- **Button hover**: brightness increase + glow appearance
- **Mood changes**: Smooth color transition `500ms ease` on indicator rings and badges
- **Chat messages**: Staggered fade-in from bottom, `50ms` delay between messages

## Do's and Don'ts

### Do
- Use generous whitespace to create breathing room
- Let the emerald accent guide attention to active/intelligent states
- Use terracotta for humanizing, emotional touches
- Keep borders subtle but present for definition
- Use rounded shapes (circles, large radii) for friendliness

### Don't
- Use pure black (`#000`) - use `#0a0a0a` for depth
- Use harsh shadows - prefer glows and borders
- Clutter the interface with too many simultaneous colors
- Use sharp corners on interactive elements
- Make mood indicators too small or subtle

## Responsive Behavior

### Breakpoints
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

### Mobile Adaptations
- Sidebar collapses to bottom tab bar or hamburger menu
- Card grid becomes single column
- Hero text scales down to `32px`
- Persona avatars reduce from `64px` to `48px`
- Touch targets minimum `44px`
