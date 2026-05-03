---
name: Translation System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#545f73'
  on-secondary: '#ffffff'
  secondary-container: '#d5e0f8'
  on-secondary-container: '#586377'
  tertiary: '#0051b1'
  on-tertiary: '#ffffff'
  tertiary-container: '#0f69dc'
  on-tertiary-container: '#edf0ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d8e3fb'
  secondary-fixed-dim: '#bcc7de'
  on-secondary-fixed: '#111c2d'
  on-secondary-fixed-variant: '#3c475a'
  tertiary-fixed: '#d8e2ff'
  tertiary-fixed-dim: '#adc6ff'
  on-tertiary-fixed: '#001a42'
  on-tertiary-fixed-variant: '#004395'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  h1:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  h2:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  h3:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  mono-sm:
    fontFamily: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  sidebar_width: 320px
  gutter: 20px
---

## Brand & Style
The brand personality of this design system is rooted in precision, reliability, and technological sophistication. It targets localization engineers and professional translators who require a tool that feels like a high-performance utility rather than a casual web app.

The aesthetic follows a **Corporate Modern** approach with elements of **Minimalism**. It mimics the structural integrity of a native desktop executable by using high-density layouts, clear visual hierarchies, and a utilitarian sidebar. The UI should evoke a sense of "quiet power"—efficient, focused, and robust enough to handle complex data transformation tasks without visual clutter.

## Colors
This design system utilizes a professional palette centered on "Slate" and "Deep Ocean" tones. The primary action color is a vibrant blue, specifically chosen to provide high contrast against the more muted slate-gray backgrounds. 

- **Primary:** A vibrant blue for main actions, active states, and focus indicators.
- **Secondary:** A deep slate blue used for the sidebar background and primary headings to provide a grounded, executable feel.
- **Neutral:** A range of cool grays (Slate) for text, borders, and secondary metadata.
- **Surface:** Pure white is reserved for cards and input fields to ensure maximum readability for translation strings and code-like data.

## Typography
The system uses **Inter** for all UI elements to ensure exceptional legibility across various display resolutions. The typographic scale is tightly controlled to maintain a high information density suitable for a desktop tool.

Headline styles use slightly tighter letter-spacing for a modern, "compact" feel. Labels and metadata should be rendered in uppercase or medium weights to differentiate them from editable content. For translation keys and technical IDs, a fallback to system monospaced fonts is recommended to avoid character confusion.

## Layout & Spacing
The layout follows a **Fixed-Fluid hybrid** model. A fixed-width sidebar (320px) on the left houses the primary configuration forms, while the main content area is fluid, expanding to fill the remainder of the window with the results dashboard.

The spacing rhythm is based on an 8px grid system, ensuring vertical alignment across form controls and table rows. Content should be grouped into cards with a standard 24px padding (`lg`), using a 20px gutter between cards to maintain a clean "application" look rather than a flat web page.

## Elevation & Depth
This design system uses **Tonal Layering** combined with **Ambient Shadows** to create a sense of depth without looking overly decorative.

1.  **Level 0 (Background):** The base application canvas uses a subtle off-white slate (`#F8FAFC`).
2.  **Level 1 (Cards/Form Containers):** Primary content surfaces are white with a 1px border (`#E2E8F0`) and a soft, diffused shadow (0px 4px 6px -1px rgba(0, 0, 0, 0.05)).
3.  **Level 2 (Modals/Dropdowns):** Overlays use a more pronounced shadow (0px 10px 15px -3px rgba(0, 0, 0, 0.1)) to clearly separate them from the dashboard beneath.
4.  **Level 3 (Focus/Active):** Highlighting is achieved through color (Primary Blue) rather than further elevation.

## Shapes
To balance the technical nature of the tool with modern UI trends, the design system utilizes **Rounded** shapes.

- Standard UI elements like buttons, input fields, and tags should use a **8px radius**.
- Large containers and cards should use a **12px radius** to soften the overall appearance of the dashboard.
- This consistent rounding creates a "friendly utility" feel that distinguishes the software from older, sharper legacy translation tools.

## Components

### Buttons
Primary buttons use the vibrant blue background with white text. Secondary buttons use a white background with a slate border and slate text. All buttons have an 8px radius and a subtle hover state that slightly darkens the background color.

### Input Fields
Inputs are defined by a 1px slate border and 8px rounded corners. The active focus state should feature a 2px vibrant blue ring with a slight outer glow to ensure the user knows exactly which part of the complex form they are interacting with.

### Cards
Cards are the primary container for the dashboard. Each card should have a clear header section with a bottom border separating the title from the content. Use cards to group related translation settings or dashboard metrics.

### Data Tables
The results dashboard should use a clean table layout with a light slate header. Rows should have a subtle hover effect (light gray background) and consistent 12px vertical padding to maintain readability of long translation strings.

### Progress & Status
Status indicators (e.g., "Success," "In Progress," "Error") should use small, rounded chips with low-saturation background tints and high-saturation text to indicate state without overwhelming the visual field.