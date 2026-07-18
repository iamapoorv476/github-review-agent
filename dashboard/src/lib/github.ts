/**
 * GitHub App install URL.
 *
 * The "Install on GitHub" CTAs point here. GitHub owns the whole install
 * flow (account picker, repo selection, confirm); we just send the user to
 * the app's public install page. After they confirm, GitHub redirects them
 * to the app's configured "Setup URL" (set that to /welcome in the GitHub
 * App settings) with ?installation_id=<id>&setup_action=install.
 *
 * Set the app slug once:
 *   # .env.local
 *   NEXT_PUBLIC_GITHUB_APP_SLUG=marginalia-app
 */
const APP_SLUG = process.env.NEXT_PUBLIC_GITHUB_APP_SLUG ?? "";

/** Public install page for the GitHub App. */
export const githubInstallUrl = APP_SLUG
  ? `https://github.com/apps/${APP_SLUG}/installations/new`
  : // Fallback keeps the button from dead-ending if the slug isn't set yet.
    "https://github.com/apps";