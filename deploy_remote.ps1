#Requires -RunAsAdministrator
<#
.SYNOPSIS
    سكريبت النشر عن بُعد - Remote Deployment Script
.DESCRIPTION
    يثبّت وكيل المراقبة الأمنية على جميع أجهزة الشبكة من جهاز واحد
.NOTES
    يجب تشغيله كـ Administrator على جهاز المسؤول
    يتطلب: PowerShell Remoting مفعل على الأجهزة المستهدفة
#>

# ============================================
#   الإعدادات
# ============================================
$ErrorActionPreference = "Continue"

# مسار ملفات المشروع على جهازك
$SourcePath = "$PSScriptRoot"

# مسار التثبيت على الأجهزة البعيدة
$RemoteInstallPath = "C:\EndpointMonitor"

# بيانات الدخول للأجهزة البعيدة (Domain Admin أو Local Admin)
$AdminUser = ""    # اتركه فاضي عشان يسألك
$AdminPass = ""    # اتركه فاضي عشان يسألك

# ملف السجل
$LogFile = "$PSScriptRoot\deployment_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

# ============================================
#   واجهة المستخدم
# ============================================
function Write-Banner {
    $banner = @"

╔══════════════════════════════════════════════════════════════╗
║     سكريبت النشر عن بُعد - Remote Deployment                ║
║     تثبيت وكيل المراقبة على جميع أجهزة الشبكة               ║
╚══════════════════════════════════════════════════════════════╝

"@
    Write-Host $banner -ForegroundColor Cyan
}

function Write-Log {
    param(
        [string]$Message,
        [string]$Color = "White",
        [string]$Level = "INFO"
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "[$timestamp] [$Level] $Message"
    Write-Host "  $Message" -ForegroundColor $Color
    $logEntry | Out-File -FilePath $LogFile -Append -Encoding UTF8
}

# ============================================
#   اكتشاف الأجهزة على الشبكة
# ============================================
function Find-NetworkDevices {
    param(
        [string]$Method = "auto"
    )

    $devices = @()

    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "  اكتشاف الأجهزة على الشبكة" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray

    # الطريقة 1: Active Directory (لو الشبكة فيها Domain)
    if ($Method -eq "auto" -or $Method -eq "ad") {
        try {
            Write-Log "جاري البحث عبر Active Directory..." "Gray"
            $adComputers = Get-ADComputer -Filter {Enabled -eq $true} -Properties Name, IPv4Address, OperatingSystem, LastLogonDate |
                Where-Object { $_.LastLogonDate -gt (Get-Date).AddDays(-30) }

            foreach ($pc in $adComputers) {
                $devices += [PSCustomObject]@{
                    Name      = $pc.Name
                    IP        = $pc.IPv4Address
                    OS        = $pc.OperatingSystem
                    Source    = "Active Directory"
                    LastSeen  = $pc.LastLogonDate
                    Status    = "Unknown"
                }
            }
            Write-Log "تم العثور على $($adComputers.Count) جهاز من Active Directory" "Green"
        }
        catch {
            Write-Log "Active Directory غير متوفر، جاري استخدام طرق بديلة..." "Yellow"
        }
    }

    # الطريقة 2: فحص الشبكة (Network Scan)
    if ($devices.Count -eq 0 -or $Method -eq "scan") {
        Write-Log "جاري فحص الشبكة..." "Gray"

        # الحصول على نطاق الشبكة
        $localIP = (Get-NetIPAddress -AddressFamily IPv4 |
            Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.PrefixOrigin -ne "WellKnown" } |
            Select-Object -First 1).IPAddress

        if ($localIP) {
            $subnet = $localIP -replace '\.\d+$', ''
            Write-Log "نطاق الشبكة: ${subnet}.0/24" "Gray"

            $jobs = @()
            for ($i = 1; $i -le 254; $i++) {
                $targetIP = "${subnet}.$i"
                $jobs += Start-Job -ScriptBlock {
                    param($ip)
                    $ping = Test-Connection -ComputerName $ip -Count 1 -Quiet -TimeoutSeconds 1
                    if ($ping) {
                        try {
                            $hostname = [System.Net.Dns]::GetHostEntry($ip).HostName
                        } catch {
                            $hostname = $ip
                        }
                        return @{ IP = $ip; Name = $hostname; Online = $true }
                    }
                    return $null
                } -ArgumentList $targetIP
            }

            Write-Log "جاري فحص 254 عنوان IP..." "Gray"

            # انتظر النتائج
            $null = $jobs | Wait-Job -Timeout 60

            foreach ($job in $jobs) {
                $result = Receive-Job -Job $job -ErrorAction SilentlyContinue
                if ($result -and $result.Online) {
                    # تجنب التكرار
                    if ($result.IP -ne $localIP) {
                        $devices += [PSCustomObject]@{
                            Name     = $result.Name
                            IP       = $result.IP
                            OS       = "Windows (Detected)"
                            Source   = "Network Scan"
                            LastSeen = Get-Date
                            Status   = "Online"
                        }
                    }
                }
            }

            $jobs | Remove-Job -Force
            Write-Log "تم العثور على $($devices.Count) جهاز على الشبكة" "Green"
        }
    }

    # الطريقة 3: ملف يدوي
    $manualFile = "$PSScriptRoot\computers.txt"
    if (Test-Path $manualFile) {
        Write-Log "جاري قراءة الأجهزة من computers.txt..." "Gray"
        $manualPCs = Get-Content $manualFile | Where-Object { $_ -and $_ -notmatch '^\s*#' }
        foreach ($pc in $manualPCs) {
            $pc = $pc.Trim()
            if ($pc) {
                $exists = $devices | Where-Object { $_.Name -eq $pc -or $_.IP -eq $pc }
                if (-not $exists) {
                    $devices += [PSCustomObject]@{
                        Name     = $pc
                        IP       = $pc
                        OS       = "Unknown"
                        Source   = "Manual List"
                        LastSeen = $null
                        Status   = "Unknown"
                    }
                }
            }
        }
        Write-Log "تمت إضافة $($manualPCs.Count) جهاز من الملف اليدوي" "Green"
    }

    return $devices
}

# ============================================
#   تفعيل PowerShell Remoting
# ============================================
function Enable-RemoteAccess {
    param([string]$ComputerName, [PSCredential]$Credential)

    try {
        # محاولة تفعيل WinRM عن بُعد باستخدام PsExec أو WMI
        $result = Invoke-WmiMethod -ComputerName $ComputerName -Credential $Credential `
            -Class Win32_Process -Name Create `
            -ArgumentList "powershell.exe -ExecutionPolicy Bypass -Command `"Enable-PSRemoting -Force -SkipNetworkProfileCheck`"" `
            -ErrorAction Stop

        if ($result.ReturnValue -eq 0) {
            Start-Sleep -Seconds 5
            return $true
        }
    }
    catch {
        return $false
    }
    return $false
}

# ============================================
#   تثبيت الوكيل على جهاز واحد
# ============================================
function Install-AgentOnRemote {
    param(
        [string]$ComputerName,
        [PSCredential]$Credential
    )

    $result = @{
        Computer = $ComputerName
        Success  = $false
        Message  = ""
        Time     = Get-Date
    }

    try {
        # التحقق من الاتصال
        if (-not (Test-Connection -ComputerName $ComputerName -Count 1 -Quiet -TimeoutSeconds 3)) {
            $result.Message = "الجهاز غير متصل"
            return $result
        }

        # التحقق من WinRM
        $winrmTest = Test-WSMan -ComputerName $ComputerName -Credential $Credential -ErrorAction Stop

        # إنشاء جلسة عن بُعد
        $session = New-PSSession -ComputerName $ComputerName -Credential $Credential -ErrorAction Stop

        # إنشاء مجلد التثبيت
        Invoke-Command -Session $session -ScriptBlock {
            param($path)
            if (-not (Test-Path $path)) {
                New-Item -Path $path -ItemType Directory -Force | Out-Null
            }
        } -ArgumentList $RemoteInstallPath

        # نسخ الملفات
        $filesToCopy = @("agent.py", "config.json", "activity_monitor.py", "stream_client.py", "access_control.py", "advanced_protection.py")
        foreach ($file in $filesToCopy) {
            $sourcefile = Join-Path $SourcePath $file
            if (Test-Path $sourcefile) {
                Copy-Item -Path $sourcefile -Destination $RemoteInstallPath -ToSession $session -Force
            }
        }

        # التحقق من وجود Python
        $pythonCheck = Invoke-Command -Session $session -ScriptBlock {
            $pythonPaths = @(
                "python",
                "python3",
                "C:\Python39\python.exe",
                "C:\Python310\python.exe",
                "C:\Python311\python.exe",
                "C:\Python312\python.exe",
                "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
                "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
                "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
                "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
            )

            foreach ($p in $pythonPaths) {
                try {
                    $ver = & $p --version 2>&1
                    if ($ver -match "Python") {
                        return @{ Found = $true; Path = $p; Version = $ver }
                    }
                } catch {}
            }
            return @{ Found = $false }
        }

        if (-not $pythonCheck.Found) {
            $result.Message = "Python غير مثبت - يحتاج تثبيت يدوي"
            # محاولة تثبيت Python تلقائياً
            Write-Log "  ⚠️ Python غير موجود على $ComputerName - جاري محاولة التثبيت..." "Yellow"

            $pythonInstalled = Invoke-Command -Session $session -ScriptBlock {
                try {
                    # تحقق من winget
                    $winget = Get-Command winget -ErrorAction Stop
                    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent 2>&1
                    Start-Sleep -Seconds 30
                    $ver = & python --version 2>&1
                    return $ver -match "Python"
                } catch {
                    return $false
                }
            }

            if (-not $pythonInstalled) {
                $result.Message = "فشل تثبيت Python تلقائياً - ثبته يدوياً"
                Remove-PSSession $session
                return $result
            }
        }

        # إنشاء مهمة مجدولة
        Invoke-Command -Session $session -ScriptBlock {
            param($installPath)

            # تثبيت المكتبات
            python -m pip install Pillow mss "python-socketio[client]" websocket-client --quiet 2>$null

            # تسجيل الموظف تلقائي
            # (يمكن تعديله لاحقاً يدوياً)

            # إنشاء ملف التشغيل
            $batContent = "@echo off`r`ncd /d `"$installPath`"`r`npython agent.py"
            Set-Content -Path "$installPath\run_monitor.bat" -Value $batContent -Encoding ASCII

            # حذف المهمة القديمة
            schtasks /delete /tn "EndpointSecurityMonitor" /f 2>$null

            # إنشاء مهمة جديدة
            schtasks /create /tn "EndpointSecurityMonitor" `
                /tr "`"$installPath\run_monitor.bat`"" `
                /sc onlogon /rl highest /f

            # تشغيل فوري
            Start-Process -FilePath "python" -ArgumentList "$installPath\agent.py" `
                -WorkingDirectory $installPath -WindowStyle Hidden

        } -ArgumentList $RemoteInstallPath

        # التحقق من التثبيت
        $verifyInstall = Invoke-Command -Session $session -ScriptBlock {
            param($path)
            $agentExists = Test-Path "$path\agent.py"
            $configExists = Test-Path "$path\config.json"
            $taskExists = (schtasks /query /tn "EndpointSecurityMonitor" 2>$null) -ne $null
            return @{
                Agent  = $agentExists
                Config = $configExists
                Task   = $taskExists
            }
        } -ArgumentList $RemoteInstallPath

        Remove-PSSession $session

        if ($verifyInstall.Agent -and $verifyInstall.Config) {
            $result.Success = $true
            $result.Message = "تم التثبيت والتشغيل بنجاح"
        } else {
            $result.Message = "فشل التحقق من التثبيت"
        }
    }
    catch {
        $result.Message = "خطأ: $($_.Exception.Message)"
    }

    return $result
}

# ============================================
#   إزالة الوكيل عن بُعد
# ============================================
function Uninstall-AgentFromRemote {
    param(
        [string]$ComputerName,
        [PSCredential]$Credential
    )

    try {
        $session = New-PSSession -ComputerName $ComputerName -Credential $Credential -ErrorAction Stop

        Invoke-Command -Session $session -ScriptBlock {
            # إيقاف العمليات
            Get-Process -Name "python" -ErrorAction SilentlyContinue |
                Where-Object { $_.CommandLine -match "agent.py" } |
                Stop-Process -Force

            # حذف المهمة المجدولة
            schtasks /delete /tn "EndpointSecurityMonitor" /f 2>$null

            # حذف الملفات
            if (Test-Path "C:\EndpointMonitor") {
                Remove-Item "C:\EndpointMonitor" -Recurse -Force
            }
        }

        Remove-PSSession $session
        return @{ Success = $true; Message = "تمت الإزالة بنجاح" }
    }
    catch {
        return @{ Success = $false; Message = $_.Exception.Message }
    }
}

# ============================================
#   فحص حالة الوكيل عن بُعد
# ============================================
function Check-AgentStatus {
    param(
        [string]$ComputerName,
        [PSCredential]$Credential
    )

    try {
        $session = New-PSSession -ComputerName $ComputerName -Credential $Credential -ErrorAction Stop

        $status = Invoke-Command -Session $session -ScriptBlock {
            $installed = Test-Path "C:\EndpointMonitor\agent.py"
            $running = Get-Process -Name "python" -ErrorAction SilentlyContinue |
                Where-Object { $_.CommandLine -match "agent.py" }
            $taskInfo = schtasks /query /tn "EndpointSecurityMonitor" /fo csv 2>$null | ConvertFrom-Csv

            return @{
                Installed  = $installed
                Running    = ($null -ne $running)
                TaskStatus = if ($taskInfo) { $taskInfo.Status } else { "Not Found" }
                PID        = if ($running) { $running.Id } else { $null }
            }
        }

        Remove-PSSession $session
        return @{ Success = $true; Data = $status }
    }
    catch {
        return @{ Success = $false; Message = $_.Exception.Message }
    }
}


# ============================================
#   القائمة الرئيسية
# ============================================
function Show-Menu {
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host "  القائمة الرئيسية" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  [1] 🔍 اكتشاف الأجهزة على الشبكة" -ForegroundColor White
    Write-Host "  [2] 📦 تثبيت الوكيل على جميع الأجهزة" -ForegroundColor White
    Write-Host "  [3] 📦 تثبيت الوكيل على جهاز محدد" -ForegroundColor White
    Write-Host "  [4] 📊 فحص حالة الوكيل على الأجهزة" -ForegroundColor White
    Write-Host "  [5] 🗑️  إزالة الوكيل من جهاز محدد" -ForegroundColor White
    Write-Host "  [6] 🗑️  إزالة الوكيل من جميع الأجهزة" -ForegroundColor White
    Write-Host "  [7] 📝 إنشاء ملف computers.txt يدوي" -ForegroundColor White
    Write-Host "  [8] ⚙️  تفعيل PowerShell Remoting على الأجهزة" -ForegroundColor White
    Write-Host "  [0] ❌ خروج" -ForegroundColor White
    Write-Host ""
}

# ============================================
#   البرنامج الرئيسي
# ============================================
Write-Banner

# طلب بيانات الدخول
Write-Host "  أدخل بيانات المسؤول (Domain Admin أو Local Admin)" -ForegroundColor Yellow
Write-Host ""

if (-not $AdminUser) {
    $cred = Get-Credential -Message "أدخل بيانات المسؤول للأجهزة البعيدة"
} else {
    $secPass = ConvertTo-SecureString $AdminPass -AsPlainText -Force
    $cred = New-Object System.Management.Automation.PSCredential($AdminUser, $secPass)
}

$discoveredDevices = @()

do {
    Show-Menu
    $choice = Read-Host "  اختر رقم"

    switch ($choice) {

        # ─── اكتشاف الأجهزة ───
        "1" {
            $discoveredDevices = Find-NetworkDevices
            if ($discoveredDevices.Count -gt 0) {
                Write-Host ""
                Write-Host "  الأجهزة المكتشفة:" -ForegroundColor Cyan
                Write-Host ""
                $i = 1
                foreach ($device in $discoveredDevices) {
                    $statusIcon = if ($device.Status -eq "Online") { "🟢" } else { "⚪" }
                    Write-Host "  $statusIcon [$i] $($device.Name) ($($device.IP)) - $($device.OS)" -ForegroundColor White
                    $i++
                }
                Write-Host ""
                Write-Log "تم اكتشاف $($discoveredDevices.Count) جهاز" "Green"
            } else {
                Write-Log "لم يتم العثور على أجهزة" "Yellow" "WARN"
                Write-Host ""
                Write-Host "  💡 نصيحة: أنشئ ملف computers.txt فيه أسماء/عناوين الأجهزة (خيار 7)" -ForegroundColor Yellow
            }
        }

        # ─── تثبيت على الكل ───
        "2" {
            if ($discoveredDevices.Count -eq 0) {
                Write-Log "اكتشف الأجهزة أولاً (خيار 1)" "Yellow" "WARN"
                continue
            }

            Write-Host ""
            Write-Host "  ⚠️  سيتم تثبيت الوكيل على $($discoveredDevices.Count) جهاز" -ForegroundColor Yellow
            $confirm = Read-Host "  هل أنت متأكد؟ (y/n)"
            if ($confirm -ne 'y') { continue }

            $successCount = 0
            $failCount = 0
            $results = @()

            foreach ($device in $discoveredDevices) {
                $target = if ($device.IP) { $device.IP } else { $device.Name }
                Write-Host ""
                Write-Log "[$($results.Count + 1)/$($discoveredDevices.Count)] جاري التثبيت على $($device.Name) ($target)..." "Cyan"

                $installResult = Install-AgentOnRemote -ComputerName $target -Credential $cred

                if ($installResult.Success) {
                    Write-Log "✅ $($device.Name): $($installResult.Message)" "Green"
                    $successCount++
                } else {
                    Write-Log "❌ $($device.Name): $($installResult.Message)" "Red" "ERROR"
                    $failCount++
                }

                $results += $installResult
            }

            Write-Host ""
            Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
            Write-Log "ملخص النشر: نجح $successCount | فشل $failCount | المجموع $($discoveredDevices.Count)" "Cyan"

            # حفظ نتائج النشر
            $results | ForEach-Object {
                $status = if ($_.Success) { "SUCCESS" } else { "FAILED" }
                "[$status] $($_.Computer): $($_.Message)"
            } | Out-File -FilePath "$PSScriptRoot\deployment_results.txt" -Encoding UTF8

            Write-Log "تم حفظ النتائج في deployment_results.txt" "Gray"
        }

        # ─── تثبيت على جهاز محدد ───
        "3" {
            Write-Host ""
            $targetPC = Read-Host "  أدخل اسم الجهاز أو عنوان IP"
            if ($targetPC) {
                Write-Log "جاري التثبيت على $targetPC..." "Cyan"
                $installResult = Install-AgentOnRemote -ComputerName $targetPC -Credential $cred
                if ($installResult.Success) {
                    Write-Log "✅ $($installResult.Message)" "Green"
                } else {
                    Write-Log "❌ $($installResult.Message)" "Red" "ERROR"
                }
            }
        }

        # ─── فحص الحالة ───
        "4" {
            if ($discoveredDevices.Count -eq 0) {
                $targetPC = Read-Host "  أدخل اسم الجهاز أو عنوان IP (أو اكتب 'all' بعد اكتشاف الأجهزة)"
                if ($targetPC) {
                    $status = Check-AgentStatus -ComputerName $targetPC -Credential $cred
                    if ($status.Success) {
                        $d = $status.Data
                        $installedIcon = if ($d.Installed) { "✅" } else { "❌" }
                        $runningIcon = if ($d.Running) { "🟢" } else { "🔴" }
                        Write-Host ""
                        Write-Host "  حالة $targetPC :" -ForegroundColor Cyan
                        Write-Host "  $installedIcon مثبت: $($d.Installed)" -ForegroundColor White
                        Write-Host "  $runningIcon شغال: $($d.Running) $(if($d.PID){"(PID: $($d.PID))"})" -ForegroundColor White
                        Write-Host "  📋 المهمة المجدولة: $($d.TaskStatus)" -ForegroundColor White
                    } else {
                        Write-Log "فشل الاتصال: $($status.Message)" "Red"
                    }
                }
            } else {
                Write-Host ""
                foreach ($device in $discoveredDevices) {
                    $target = if ($device.IP) { $device.IP } else { $device.Name }
                    $status = Check-AgentStatus -ComputerName $target -Credential $cred
                    if ($status.Success) {
                        $d = $status.Data
                        $icon = if ($d.Running) { "🟢" } elseif ($d.Installed) { "🟡" } else { "🔴" }
                        Write-Host "  $icon $($device.Name): مثبت=$($d.Installed) | شغال=$($d.Running) | المهمة=$($d.TaskStatus)" -ForegroundColor White
                    } else {
                        Write-Host "  ⚪ $($device.Name): غير متصل" -ForegroundColor Gray
                    }
                }
            }
        }

        # ─── إزالة من جهاز ───
        "5" {
            Write-Host ""
            $targetPC = Read-Host "  أدخل اسم الجهاز أو عنوان IP"
            if ($targetPC) {
                $confirm = Read-Host "  ⚠️ هل أنت متأكد من إزالة الوكيل من ${targetPC}؟ (y/n)"
                if ($confirm -eq 'y') {
                    $uninstallResult = Uninstall-AgentFromRemote -ComputerName $targetPC -Credential $cred
                    if ($uninstallResult.Success) {
                        Write-Log "✅ $($uninstallResult.Message)" "Green"
                    } else {
                        Write-Log "❌ $($uninstallResult.Message)" "Red"
                    }
                }
            }
        }

        # ─── إزالة من الكل ───
        "6" {
            if ($discoveredDevices.Count -eq 0) {
                Write-Log "اكتشف الأجهزة أولاً (خيار 1)" "Yellow" "WARN"
                continue
            }

            Write-Host ""
            Write-Host "  ⚠️  سيتم إزالة الوكيل من $($discoveredDevices.Count) جهاز" -ForegroundColor Red
            $confirm = Read-Host "  هل أنت متأكد؟ (y/n)"
            if ($confirm -ne 'y') { continue }

            foreach ($device in $discoveredDevices) {
                $target = if ($device.IP) { $device.IP } else { $device.Name }
                Write-Log "جاري الإزالة من $($device.Name)..." "Yellow"
                $result = Uninstall-AgentFromRemote -ComputerName $target -Credential $cred
                $icon = if ($result.Success) { "✅" } else { "❌" }
                Write-Log "$icon $($device.Name): $($result.Message)" $(if($result.Success){"Green"}else{"Red"})
            }
        }

        # ─── إنشاء ملف يدوي ───
        "7" {
            $filePath = "$PSScriptRoot\computers.txt"
            $template = @"
# ══════════════════════════════════════════════════════
# قائمة أجهزة الشركة - Endpoint Monitor
# أضف اسم كل جهاز أو عنوان IP في سطر منفصل
# الأسطر اللي تبدأ بـ # تعتبر تعليقات
# ══════════════════════════════════════════════════════

# أمثلة:
# PC-RECEPTION
# PC-ACCOUNTING
# 192.168.1.100
# 192.168.1.101

"@
            Set-Content -Path $filePath -Value $template -Encoding UTF8
            Write-Log "تم إنشاء $filePath" "Green"
            Write-Host "  📝 افتح الملف وأضف أسماء/عناوين الأجهزة" -ForegroundColor Yellow
            Start-Process notepad $filePath
        }

        # ─── تفعيل PS Remoting ───
        "8" {
            Write-Host ""
            Write-Host "  لتفعيل PowerShell Remoting على الأجهزة:" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "  الطريقة 1: عبر Group Policy (الأفضل للشبكات الكبيرة)" -ForegroundColor Cyan
            Write-Host "    Computer Config > Policies > Admin Templates > " -ForegroundColor Gray
            Write-Host "    Windows Components > Windows Remote Management > " -ForegroundColor Gray
            Write-Host "    WinRM Service > Allow remote server management = Enabled" -ForegroundColor Gray
            Write-Host ""
            Write-Host "  الطريقة 2: يدوياً على كل جهاز (افتح PowerShell كـ Admin):" -ForegroundColor Cyan
            Write-Host "    Enable-PSRemoting -Force -SkipNetworkProfileCheck" -ForegroundColor White
            Write-Host "    Set-Item WSMan:\localhost\Client\TrustedHosts -Value '*' -Force" -ForegroundColor White
            Write-Host ""
            Write-Host "  الطريقة 3: عبر هذا السكريبت (لو عندك WMI access):" -ForegroundColor Cyan
            $targetPC = Read-Host "  أدخل اسم الجهاز (أو Enter للرجوع)"
            if ($targetPC) {
                Write-Log "جاري محاولة تفعيل PS Remoting على $targetPC..." "Yellow"
                $enabled = Enable-RemoteAccess -ComputerName $targetPC -Credential $cred
                if ($enabled) {
                    Write-Log "✅ تم التفعيل بنجاح" "Green"
                } else {
                    Write-Log "❌ فشل التفعيل - جرب يدوياً" "Red"
                }
            }
        }

        "0" {
            Write-Host ""
            Write-Host "  👋 شكراً لاستخدامك سكريبت النشر!" -ForegroundColor Cyan
            Write-Host ""
        }

        default {
            Write-Host "  اختيار غير صحيح" -ForegroundColor Red
        }
    }

} while ($choice -ne "0")
