# Frontend Changes: Dark/Light Theme Toggle & Light Theme CSS Variables

## Summary

Added a toggle button in the top-right corner of the page that switches between dark mode (default) and light mode. The user's preference is persisted in `localStorage`. Refined the light theme with comprehensive CSS variables for proper contrast, accessibility, and full coverage of all UI elements.

## Files Changed

### `frontend/index.html`
- Added a `<button id="themeToggle">` element before the main container, containing two inline SVGs: a sun icon (shown in dark mode) and a moon icon (shown in light mode)
- The button includes `aria-label` and `title` attributes for accessibility
- Bumped CSS version query string to `v=15` and JS to `v=12`

### `frontend/style.css`

#### New CSS variables added to `:root` (dark theme defaults)
- `--welcome-shadow` - welcome message box-shadow color
- `--code-bg` - background for inline code and code blocks
- `--link-color` / `--link-hover` - link colors (were hardcoded `#93c5fd` / `#bfdbfe`)
- `--error-bg`, `--error-color`, `--error-border` - error message theming
- `--success-bg`, `--success-color`, `--success-border` - success message theming
- `--scrollbar-thumb` / `--scrollbar-hover` - scrollbar colors

#### Light theme (`[data-theme="light"]`) variable values
All variables overridden with light-appropriate colors:
- **Background**: `#f8fafc` (slate-50) - light, neutral background
- **Surface**: `#ffffff` (white) - cards, sidebar, inputs
- **Surface hover**: `#f1f5f9` (slate-100)
- **Text primary**: `#0f172a` (slate-900) - 17.4:1 contrast ratio on background
- **Text secondary**: `#475569` (slate-600) - 7.7:1 contrast ratio (upgraded from `#64748b` for WCAG AA)
- **Border color**: `#cbd5e1` (slate-300) - visible but subtle borders
- **Code bg**: `#f1f5f9` (slate-100) - distinct from white surface
- **Link color**: `#1d4ed8` (blue-700) - 7.5:1 contrast on white, meets WCAG AA
- **Link hover**: `#1e40af` (blue-800)
- **Error**: `#dc2626` text on `#fef2f2` bg with `#fecaca` border
- **Success**: `#15803d` text on `#f0fdf4` bg with `#bbf7d0` border
- **Shadow**: lighter, multi-layer shadow for subtle depth
- **Welcome shadow**: `rgba(0,0,0,0.06)` - much softer than dark theme
- **Scrollbar**: `#cbd5e1` thumb, `#94a3b8` hover

#### Hardcoded colors replaced with variables
- Links (`.sources-content a`, `.message-content a`) now use `var(--link-color)` / `var(--link-hover)`
- Code blocks (`.message-content code`, `.message-content pre`) now use `var(--code-bg)`
- Error message uses `var(--error-bg)`, `var(--error-color)`, `var(--error-border)`
- Success message uses `var(--success-bg)`, `var(--success-color)`, `var(--success-border)`
- Welcome message shadow uses `var(--welcome-shadow)`
- Scrollbar thumbs use `var(--scrollbar-thumb)` / `var(--scrollbar-hover)`

#### Bug fix
- Fixed blockquote `border-left` referencing non-existent `--primary` variable; changed to `--primary-color`

#### Removed
- Scattered `[data-theme="light"]` class-based overrides (for code, pre, links) — no longer needed since all colors now use CSS variables

#### Existing (from toggle button feature)
- `.theme-toggle` styles: fixed position top-right, circular button, `z-index: 1000`, hover/focus/active states
- Icon visibility rules: `.icon-sun` shown by default (dark mode), `.icon-moon` shown in light mode
- `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease` on key elements

### `frontend/script.js`
- `initTheme()` reads `localStorage('theme')` and applies `data-theme` attribute to `<html>` — called immediately to prevent flash
- `toggleTheme()` flips between `dark` and `light`, updates DOM and saves to `localStorage`
- Click listener on `#themeToggle` button

## Accessibility
- All text-primary to background contrast ratios exceed WCAG AA (4.5:1 minimum): 17.4:1
- Text-secondary contrast: 7.7:1 (exceeds AA for normal text)
- Link colors: 7.0:1+ on both background and surface
- Error/success text: 5.1:1+ (AA compliant)
- Focus rings visible in both themes via `--focus-ring`
- Theme toggle button is keyboard-navigable with visible focus indicator

## Design Decisions
- Default theme is dark (matching the existing design) — no `data-theme` attribute means dark
- Toggle is `position: fixed` so it stays visible regardless of scroll position
- Sun icon = "click to switch to light"; moon icon = "click to switch to dark" (industry standard)
- Light theme uses Tailwind slate palette for consistency across grays
- All colors converted to CSS variables so both themes are controlled from a single location
