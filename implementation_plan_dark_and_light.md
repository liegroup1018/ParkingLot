# Dark Mode for admin_ui/dashboard.html

Add a seamless light / dark mode toggle to the admin dashboard, with the user's preference persisted in `localStorage` and applied instantly on page load (no flash).

---

## Proposed Changes

### Part 1 — Tailwind dark-mode configuration
#### [MODIFY] `<head>` → Tailwind config block (lines 9–23)

Enable Tailwind's `class`-based dark mode by adding `darkMode: 'class'` to the config object.  
This makes every `dark:*` utility class work when `<html>` has the `dark` class.

```diff
 tailwind.config = {
+    darkMode: 'class',
     theme: { extend: { colors: { brand: { … } } } }
 }
```

---

### Part 2 — Toggle button in the navbar
#### [MODIFY] `<nav>` (lines 26–38)

Insert a sun/moon icon button in the right-hand nav item cluster, next to the username badge and Sign Out link.  
- Uses two inline SVGs (sun for light mode, moon for dark mode) that swap visibility via JS.  
- Accessible: `aria-label`, smooth `transition` on hover.

---

### Part 3 — Theme initialization script (before `</head>`)
#### [MODIFY] `<head>` (lines 3–24)

Add an **inline** `<script>` that reads `localStorage.getItem('theme')` and immediately sets or removes the `dark` class on `<html>` — preventing any flash of unstyled content (FOUC).

```html
<script>
  if (localStorage.theme === 'dark' ||
      (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  }
</script>
```

---

### Part 4 — `<body>` and structural elements
#### [MODIFY] `<body>` (line 25)

Add dark-mode variants:

| Element | Light class | Added dark class |
|---|---|---|
| `<body>` | `bg-gray-50 text-gray-800` | `dark:bg-gray-900 dark:text-gray-100` |
| `<nav>` | `bg-brand-900` | (already dark, but add `dark:border-gray-700`) |
| Page `<h1>` | `text-gray-900` | `dark:text-white` |
| Refresh button | `bg-gray-200 text-gray-700` | `dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600` |

---

### Part 5 — KPI cards
#### [MODIFY] KPI grid (lines 50–73)

Each card is `bg-white shadow-md`. Add:
- `dark:bg-gray-800 dark:shadow-gray-900`
- KPI labels: `dark:text-gray-400`
- KPI values: `dark:text-white`
- Pricing button: `dark:bg-indigo-900 dark:text-indigo-200 dark:hover:bg-indigo-800`

---

### Part 6 — Chart panels
#### [MODIFY] Charts grid + peak hours panel (lines 76–100)

Each chart wrapper is `bg-white shadow`. Add `dark:bg-gray-800 dark:shadow-gray-900`.  
Chart headings `text-gray-900` → also `dark:text-white`.

---

### Part 7 — Users table panel
#### [MODIFY] Staff & User Management section (lines 102–127)

- Panel wrapper: `dark:bg-gray-800`  
- Heading: `dark:text-white`
- Table header `bg-gray-50` → `dark:bg-gray-700`
- `divide-gray-200` → `dark:divide-gray-700`
- Header cells `text-gray-500` → `dark:text-gray-400`
- Table body rows created by JS (lines 379–390): update the `innerHTML` template to include dark variants for `text-gray-500`, `text-gray-900`, etc.

---

### Part 8 — Modals (Pricing + Create User)
#### [MODIFY] `#pricingModal` + `#userModal` (lines 130–215)

- Overlay stays dark (`bg-gray-900 bg-opacity-75`) — fine for both modes.
- Inner panel `bg-white` → `dark:bg-gray-800`
- Modal titles `text-gray-900` → `dark:text-white`
- Labels `text-gray-700` → `dark:text-gray-300`
- Inputs `bg-gray-50 border-gray-300` → `dark:bg-gray-700 dark:border-gray-600 dark:text-white dark:placeholder-gray-400`
- Cancel button: `border-gray-300 text-gray-700 bg-white` → `dark:border-gray-600 dark:text-gray-200 dark:bg-gray-700`
- Close (×) icon: `text-gray-400 hover:text-gray-600` → `dark:hover:text-gray-200`

---

### Part 9 — `toggleTheme()` JS function
#### [MODIFY] `<script>` block (lines 217–575)

Add a small utility:

```js
function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    updateThemeIcon();
}
function updateThemeIcon() {
    const isDark = document.documentElement.classList.contains('dark');
    document.getElementById('icon-sun').classList.toggle('hidden', !isDark);
    document.getElementById('icon-moon').classList.toggle('hidden', isDark);
}
// Run once on load
document.addEventListener('DOMContentLoaded', updateThemeIcon);
```

---

## Verification Plan

### Manual
1. Open the dashboard in a browser.
2. Click the toggle — page should switch to dark mode instantly; preference persists on reload.
3. Use browser DevTools → System color scheme override → verify auto-detection works on first visit.
4. Open both modals in dark mode — all fields, labels, buttons should look correct.
5. Check table rows (dynamically injected by JS) render with dark-safe colors.
