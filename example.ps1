#requires -RunAsAdministrator
param(
    [switch]$Hello,
    [string]$Name = "World"
)

Write-Host "Hello, $Name!" -ForegroundColor Cyan
if ($Hello) {
    Write-Host "You passed -Hello switch!" -ForegroundColor Green
}
