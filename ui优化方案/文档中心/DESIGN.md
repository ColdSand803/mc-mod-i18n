---
name: Linguistic Precision System
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#434655'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#943700'
  on-tertiary: '#ffffff'
  tertiary-container: '#bc4800'
  on-tertiary-container: '#ffede6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#ffdbcd'
  tertiary-fixed-dim: '#ffb596'
  on-tertiary-fixed: '#360f00'
  on-tertiary-fixed-variant: '#7d2d00'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 30px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  sidebar-width: 260px
  content-max-width: 1280px
  container-padding: 2rem
  gutter: 1.5rem
  stack-sm: 0.5rem
  stack-md: 1rem
  stack-lg: 2rem
---

## Brand & Style
The brand personality is professional, utilitarian, and highly organized, reflecting the complexity of localization workflows. This design system prioritizes clarity and efficiency, ensuring that linguistic data remains the focal point without unnecessary visual noise.

The aesthetic follows a **Modern Corporate** style. It utilizes a refined color palette and a structured layout to build trust and reduce cognitive load. The UI feels like a high-performance instrument—stable, predictable, and clean—designed for long-session productivity. Significant whitespace and subtle borders are used to separate logical sections, creating a sense of "digital workspace" rather than a mere website.

## Colors
The color palette is built on a foundation of "Action Blue" and "Deep Slate." 

- **Primary Blue (#2563EB):** Reserved for primary actions, active navigation states, and key interactive elements. It represents progress and reliability.
- **Surface Neutrals:** We use a light-gray background (`#F1F5F9` or `#F8FAFC`) to provide contrast against pure white (`#FFFFFF`) content containers. This layering creates a clear distinction between the workspace and the content.
- **Text Layers:** Primary text is set in `#0F172A` for maximum legibility, while secondary metadata uses `#64748B`.
- **Semantic Colors:** Translation statuses utilize industry-standard semantic colors (Green for "Translated," Amber for "Review Needed," Red for "Error").

## Typography
The typography system uses a pairing of **Hanken Grotesk** for structural headings and **Inter** for long-form reading and interface labels. 

Headlines are bold and authoritative, using a tight letter-spacing to maintain a modern look. The body text is optimized for readability in a translation context, where users must distinguish between subtle punctuation and character differences. For technical metadata, keys, or code snippets, **JetBrains Mono** is used to provide a clear distinction from the translated text strings.

## Layout & Spacing
The layout follows a **Fixed Sidebar + Fluid Content** model. 

1.  **Sidebar:** A fixed 260px left-hand navigation bar provides global context. It uses a slightly darker neutral or subtle transparency to separate it from the work area.
2.  **Main Stage:** The content area is centered with a max-width of 1280px to ensure line lengths remain readable for documentation. 
3.  **Grid:** Within containers, a 12-column system is used for data tables and form layouts.
4.  **Density:** We utilize a "Compact" spacing rhythm (`8px` increments). This allows for high-density information display without feeling cramped, essential for managing large translation catalogs.

## Elevation & Depth
This design system avoids heavy shadows, opting instead for **Tonal Layering** and **Low-Contrast Outlines**.

- **Level 0 (Background):** The base application canvas, colored in the lightest neutral gray.
- **Level 1 (Cards/Panels):** Pure white surfaces with a 1px border of `#E2E8F0`. These containers hold the primary content.
- **Level 2 (Popovers/Modals):** Elements that float above the surface use a soft, highly diffused shadow (`0 10px 15px -3px rgba(0, 0, 0, 0.1)`) and a crisp border.
- **Active State:** Elements being edited or focused are highlighted with a 2px Primary Blue border rather than depth changes.

## Shapes
Shapes are disciplined and professional. We use a **Soft (4px-12px)** rounding system.

- **Small Components:** Buttons and input fields use a `4px` radius (`rounded-sm`).
- **Containers:** Content cards and sidebars use a `8px` or `12px` radius (`rounded-lg`) to soften the interface slightly while maintaining a structured, architectural feel.
- **Selection Indicators:** Active navigation items use a subtle rounded vertical pill on the left edge to denote focus.

## Components
- **Buttons:** Primary buttons are solid Blue with White text. Secondary buttons use a white background with a gray border. Use "compact" padding for toolbar actions.
- **Cards:** White backgrounds, subtle borders, and `stack-md` padding. Headers within cards should have a divider line separating them from the body.
- **Input Fields:** Use a subtle light-gray fill on idle, turning white with a primary blue border on focus. Labels are always positioned above the field in `label-md` style.
- **Status Chips:** Small, low-saturation backgrounds with high-saturation text (e.g., light green background with dark green text) to indicate translation progress.
- **Sidebar Items:** Clean list items with 16px icons. The active state should use a light-blue tint or a bold primary blue text weight.
- **Data Tables:** Borderless rows with a subtle divider line. The header row should have a light-gray background to define the structure.