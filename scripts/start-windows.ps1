$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot
function Check-DockerExit {
    if ($LASTEXITCODE -ne 0) { throw 'Docker command failed. Read its output above.' }
}
docker info | Out-Null
Check-DockerExit
docker compose version
Check-DockerExit
if (!(Test-Path -LiteralPath '.env')) {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $dbPassword = [BitConverter]::ToString($bytes).Replace('-', '').ToLowerInvariant()
    Set-Content -LiteralPath '.env' -Value "POSTGRES_PASSWORD=$dbPassword" -Encoding ASCII
    Remove-Variable dbPassword
}
# Download pinned Linux wheels inside Docker; Python is not needed on Windows.
docker run --rm --platform linux/amd64 --mount "type=bind,source=$repoRoot,target=/workspace" --workdir /workspace python:3.12-slim sh ./scripts/prepare-wheels.sh
Check-DockerExit
docker compose -f compose.windows.yaml build app
Check-DockerExit
docker compose -f compose.windows.yaml up -d --wait
Check-DockerExit
docker compose -f compose.windows.yaml cp tls:/data/caddy/pki/authorities/local/root.crt ./premier-root.crt
Check-DockerExit
Write-Host 'Started. Follow docs/WINDOWS_TEST.md to trust HTTPS and create the first admin.'
