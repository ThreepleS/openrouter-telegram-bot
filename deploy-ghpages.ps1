# Deploy frontend to GitHub Pages.
# Run:  .\deploy-ghpages.ps1   (after: gh auth login)
# Repo is PUBLIC (GitHub Pages free only for public repos). No secrets here.

param(
  [string]$RepoName = "ai-app-frontend",
  [string]$RepoDir  = "gh-pages"
)

$ErrorActionPreference = "Stop"
$root = (Get-Item $PSScriptRoot).FullName
$dir  = Join-Path $root $RepoDir
if (-not (Test-Path $dir)) { Write-Error "No folder $dir"; exit 1 }

Set-Location $dir

$auth = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "Login required first: gh auth login" -ForegroundColor Red
  exit 1
}

git init -q
git checkout -q -B gh-pages
git add -A
git commit -q -m "frontend: deploy to GitHub Pages"
if ($LASTEXITCODE -ne 0) { Write-Host "Nothing to commit (already up to date)." }

Write-Host "Creating public repo '$RepoName'..." -ForegroundColor Cyan
gh repo create $RepoName --public --source . --push 2>&1

$owner = (gh api user --jq ".login")
Write-Host "Enabling GitHub Pages (branch gh-pages)..." -ForegroundColor Cyan
gh api -X POST "repos/$owner/$RepoName/pages" `
  -f "source[branch]=gh-pages" `
  -f "source[path]=/" 2>&1 | Out-Null

Write-Host ""
Write-Host "Done. In 1-2 min the frontend will be at:" -ForegroundColor Green
Write-Host "  https://$owner.github.io/$RepoName/" -ForegroundColor Yellow
Write-Host ""
Write-Host "To bind to your backend tunnel, open:" -ForegroundColor Cyan
Write-Host "  https://$owner.github.io/$RepoName/?api=https://YOUR-TUNNEL" -ForegroundColor Yellow
