<#
.SYNOPSIS
  Sentinel task runner for Windows PowerShell. Mirrors the Makefile targets.

.EXAMPLE
  .\make.ps1 up
  .\make.ps1 demo
  .\make.ps1 test
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet("up", "down", "deploy", "demo", "samples", "test", "logs", "alerts", "dlq", "dashboard", "reset", "help")]
    [string]$Target = "help"
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$tf = Join-Path $root "terraform"

function Invoke-Up {
    docker compose up -d --wait
    Invoke-Deploy
}

function Invoke-Deploy {
    Push-Location $tf
    try {
        terraform init -input=false
        terraform apply -auto-approve
    }
    finally { Pop-Location }
}

function Invoke-Samples { python (Join-Path $root "scripts\make_samples.py") }

function Invoke-Demo {
    Invoke-Samples
    python (Join-Path $root "scripts\demo.py")
}

function Invoke-Test { python -m pytest -q }

function Invoke-Logs { docker compose logs -f localstack }

function Invoke-Alerts { python (Join-Path $root "scripts\alerts.py") }

function Invoke-Dlq {
    Push-Location $tf
    try { $url = terraform output -raw scan_dlq_url }
    finally { Pop-Location }
    awslocal sqs get-queue-attributes --queue-url $url --attribute-names ApproximateNumberOfMessages
}

function Invoke-Dashboard {
    Write-Host "Dashboard at http://localhost:8080 (Ctrl+C to stop)"
    python (Join-Path $root "dashboard\server.py")
}

function Invoke-Down { docker compose down }

function Invoke-Reset {
    docker compose down -v
    Remove-Item -Recurse -Force (Join-Path $tf ".terraform"), (Join-Path $tf "build") -ErrorAction SilentlyContinue
    Remove-Item -Force (Join-Path $tf "terraform.tfstate*") -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $root "samples") -ErrorAction SilentlyContinue
}

function Invoke-Help {
    @"
Sentinel tasks (Windows):
  .\make.ps1 up       Start LocalStack and deploy everything
  .\make.ps1 deploy   terraform init + apply
  .\make.ps1 demo     Upload samples and print the verdict table
  .\make.ps1 samples  Generate harmless sample files
  .\make.ps1 test     Run unit tests
  .\make.ps1 logs     Tail LocalStack logs
  .\make.ps1 alerts   Show SECURITY ALERT lines
  .\make.ps1 dlq       Show approximate DLQ depth
  .\make.ps1 dashboard Serve the visual dashboard at http://localhost:8080
  .\make.ps1 down     Stop LocalStack
  .\make.ps1 reset    Tear down everything (volumes + terraform state)
"@
}

switch ($Target) {
    "up"      { Invoke-Up }
    "down"    { Invoke-Down }
    "deploy"  { Invoke-Deploy }
    "demo"    { Invoke-Demo }
    "samples" { Invoke-Samples }
    "test"    { Invoke-Test }
    "logs"    { Invoke-Logs }
    "alerts"  { Invoke-Alerts }
    "dlq"       { Invoke-Dlq }
    "dashboard" { Invoke-Dashboard }
    "reset"     { Invoke-Reset }
    default   { Invoke-Help }
}
