# Builds the Atlas3K download: Atlas3K.exe (editor) + Atlas3K.Cli.exe (headless builder), self-contained
# win-x64 (no .NET install needed), plus the read-me files, in dist\Atlas3K-<version>\ and a zip of it with its
# SHA-256 (<zip>.sha256), which the in-app updater checks.
#   powershell -ExecutionPolicy Bypass -File tools\publish.ps1 [-NoZip] [-Channel stable|unstable] [-Release [-NotesFile f]]
# -Channel: the update channel the build belongs to (default: unstable for a pre-release version such as
#   0.2.0-beta.1, stable for 0.2.0). Stable releases need an empty VersionSuffix in Directory.Build.props.
# -Release: also tag v<version> and publish a GitHub release (gh) with the zip and its .sha256 - a pre-release on the
#   unstable channel, a full release on stable. Installs on that channel offer it as an update.
param([switch]$NoZip, [ValidateSet("", "stable", "unstable")][string]$Channel = "", [switch]$Release, [string]$NotesFile = "")
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
# the version carries the commit (Directory.Build.props runs git); Git for Windows is often not on PowerShell's PATH
if (-not (Get-Command git -ErrorAction SilentlyContinue) -and (Test-Path "$env:ProgramFiles\Git\cmd\git.exe")) {
    $env:PATH = "$env:ProgramFiles\Git\cmd;$env:PATH"
}
[xml]$props = Get-Content (Join-Path $root "Directory.Build.props")
$group = $props.Project.PropertyGroup | Select-Object -First 1
$version = if ($group.VersionSuffix) { "$($group.VersionPrefix)-$($group.VersionSuffix)" } else { "$($group.VersionPrefix)" }
if (-not $Channel) { $Channel = if ($group.VersionSuffix) { "unstable" } else { "stable" } }
if ($Channel -eq "stable" -and $group.VersionSuffix) { throw "a stable release needs a version without suffix (Directory.Build.props VersionSuffix is '$($group.VersionSuffix)')" }
if ($Release -and $NoZip) { throw "-Release needs the zip" }
$out = Join-Path $root "dist\Atlas3K-$version"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }

foreach ($project in "src\Atlas3K.App\Atlas3K.App.csproj", "src\Atlas3K.Cli\Atlas3K.Cli.csproj") {
    Write-Host "publishing $project"
    dotnet publish (Join-Path $root $project) -c Release -r win-x64 --self-contained true -o $out -p:DebugType=none -p:GenerateDocumentationFile=false -nologo -v q
    if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed for $project" }
}
foreach ($doc in "LICENSE", "README.md", "CHANGELOG.md", "KNOWN_ISSUES.md", "THIRD_PARTY_NOTICES.md") {
    Copy-Item (Join-Path $root $doc) $out
}
# nothing machine-specific may ship
Get-ChildItem $out -Include *.pdb, *.xml -Recurse | Where-Object { $_.Name -notlike "*.deps.json" } | Remove-Item -Force -ErrorAction SilentlyContinue
# marks a release install: only these update themselves (a source build never does)
@{ version = $version; channel = $Channel } | ConvertTo-Json | Set-Content -Path (Join-Path $out "atlas3k-install.json") -Encoding utf8

$size = (Get-ChildItem $out -Recurse | Measure-Object Length -Sum).Sum / 1MB
Write-Host ("{0}: {1:N0} MB ({2} channel)" -f $out, $size, $Channel)
if ($NoZip) { return }
$zip = "$out.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$out\*" -DestinationPath $zip -CompressionLevel Optimal
$sha = (Get-FileHash $zip -Algorithm SHA256).Hash
Set-Content -Path "$zip.sha256" -Value "$sha  $(Split-Path -Leaf $zip)" -Encoding ascii
Write-Host ("{0}: {1:N0} MB, SHA-256 {2}" -f $zip, ((Get-Item $zip).Length / 1MB), $sha)

if ($Release) {
    $tag = "v$version"
    $notes = if ($NotesFile) { Get-Content $NotesFile -Raw } else { "Atlas3K $version ($Channel channel)." }
    $notes += "`n`nSHA-256 of the zip: ``$sha``"
    $notesPath = Join-Path $env:TEMP "atlas3k_release_notes.md"
    Set-Content -Path $notesPath -Value $notes -Encoding utf8
    $ghArgs = @("release", "create", $tag, $zip, "$zip.sha256", "--title", "Atlas3K $version", "--notes-file", $notesPath, "--target", (git -C $root rev-parse HEAD))
    if ($Channel -eq "unstable") { $ghArgs += "--prerelease" } else { $ghArgs += "--latest" }
    & gh @ghArgs
    if ($LASTEXITCODE -ne 0) { throw "gh release create failed" }
    Write-Host "released $tag on the $Channel channel"
}
