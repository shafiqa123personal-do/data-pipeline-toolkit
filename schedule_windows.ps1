# Registers two Windows Task Scheduler jobs for this project.
# Run once in PowerShell from the project folder:  .\schedule_windows.ps1
$project = $PSScriptRoot
$python = (Get-Command python).Source

$books = New-ScheduledTaskAction -Execute $python -Argument "run.py books --pages 50" -WorkingDirectory $project
$daily = New-ScheduledTaskTrigger -Daily -At 9:00am
Register-ScheduledTask -TaskName "Data Pipeline - Books" -Action $books -Trigger $daily -Force | Out-Null

$invoices = New-ScheduledTaskAction -Execute $python -Argument "run.py invoices" -WorkingDirectory $project
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "Data Pipeline - Invoices" -Action $invoices -Trigger $hourly -Force | Out-Null

Write-Host "Done. Two tasks registered - see them in Task Scheduler (taskschd.msc)."
