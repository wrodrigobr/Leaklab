# Monitor em tempo real da fila GTO
# Uso: .\scripts\watch_gto_queue.ps1
param([int]$IntervalSeconds = 5)

$db     = (Resolve-Path "$PSScriptRoot\..\data\leaklab.db").Path
$script = (Resolve-Path "$PSScriptRoot\watch_gto_queue.py").Path

Clear-Host
Write-Host "=== GTO QUEUE MONITOR === (Ctrl+C para sair, intervalo: ${IntervalSeconds}s)" -ForegroundColor Cyan
Write-Host ""

while ($true) {
    $output = python $script $db 2>&1

    Clear-Host
    Write-Host "=== GTO QUEUE MONITOR === (Ctrl+C para sair)" -ForegroundColor Cyan
    Write-Host ""

    foreach ($line in $output) {
        if     ($line -match "CONCLUIDO")              { Write-Host $line -ForegroundColor Green  }
        elseif ($line -match "pending=[1-9]")          { Write-Host $line -ForegroundColor Yellow }
        elseif ($line -match "failed=[1-9]")           { Write-Host $line -ForegroundColor Red    }
        elseif ($line -match "sem GTO: 0/")            { Write-Host $line -ForegroundColor Green  }
        elseif ($line -match "sem GTO: [1-9]")         { Write-Host $line -ForegroundColor Yellow }
        else                                           { Write-Host $line }
    }

    Write-Host ""
    Write-Host "Atualizando em ${IntervalSeconds}s..." -ForegroundColor DarkGray
    Start-Sleep -Seconds $IntervalSeconds
}
