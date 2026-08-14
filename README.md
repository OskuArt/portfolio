# Kseniia Smirnova — Portfolio

Static portfolio deployed on Render and automatically synchronized with Behance.

## Automatic Behance sync

The workflow `.github/workflows/update-behance.yml` runs every day at **00:07 Europe/Moscow** and can also be started manually from the **Actions** tab.

It:
- reads every public case from `https://www.behance.net/oskuhallaART`;
- follows Behance pagination;
- adds newly published cases to `projects.json`;
- downloads a high-quality project preview into `assets/project-previews/` when possible;
- preserves hand-edited metadata/categories for projects already in `projects.json`;
- commits changes to `main`, which triggers the existing Render auto-deploy;
- fails safely instead of wiping the list if Behance suddenly returns an incomplete profile.

## Important

No Behance API key is required. The sync reads the public profile HTML, so if Behance substantially changes its page structure in the future, `scripts/update_behance.py` may need a small update.

The workflow also creates a tiny keepalive commit at most once every 30 days. This helps prevent GitHub from disabling scheduled workflows in a public repository after a long period of repository inactivity.

## Manual sync

GitHub → **Actions** → **Sync Behance portfolio** → **Run workflow**.

Use this right after publishing a new Behance case if you do not want to wait for the nightly sync.

## Render

Keep the current Render Static Site settings:
- Branch: `main`
- Root Directory: empty
- Build Command: `echo "No build required"`
- Publish Directory: `.`

Render will redeploy when the GitHub Action commits an updated `projects.json` or new preview image.
