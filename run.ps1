# Проверка прав администратора
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run with administrator privileges."
    exit
}

# Путь к виртуальной среде
$venvPath = "venv\Scripts\activate.ps1"

# Активация виртуальной среды
if (-Not (Test-Path $venvPath)) {
   Write-Error "Virtual environment not found. Please make sure 'venv' folder exists."
    exit
} else {
    Write-Host "Activating virtual environment..."
    . $venvPath  # Использование точки (.) для выполнения скрипта в текущем контексте
}

# Путь к файлу Python скрипта
$pythonScriptPath = ".\src\fast_api\main.py"

# Уникальное имя мьютекса
$mutexName = "Global\FastAPIServerManagerMutex"
$mutex = $null

# Функция для вызова python скрипта
function Invoke-PythonScript {
    param (
        [string]$Command,
        [string]$Description
    )
     Write-Host "Executing $($Description): $($Command)"
    try {
        Start-Process -FilePath "powershell" -ArgumentList "-NoProfile", "-NonInteractive", "-Command", $Command -Wait -PassThru | Out-Null
         if ($LASTEXITCODE -ne 0) {
            throw "Python script failed with exit code $($LASTEXITCODE)."
        }
     } catch {
        Write-Error "Failed to $($Description): $($_.Exception.Message)"
    }
}

try {
    # Создаем мьютекс
    $mutex = New-Object System.Threading.Mutex($False, $mutexName)
    # Пытаемся получить мьютекс
    $acquiredMutex = $mutex.WaitOne(0, $False)

    if (!$acquiredMutex) {
        Write-Error "Another instance of this script is already running."
        exit
    }

    # Функция для запуска сервера
    function Start-FastAPIServer {
        param (
            [int]$Port = 8000,
            [string]$serverHost = "0.0.0.0"
        )
        Write-Host "Starting FastAPI server on port $Port and host $serverHost..."
        $command = "python $pythonScriptPath --command start --port $Port --host $serverHost"
        Invoke-PythonScript -Command $command -Description "Start server on port $Port and host $serverHost"
        Write-Host "Server started successfully."
    }

    # Функция для остановки сервера
    function Stop-FastAPIServer {
        param (
            [int]$Port = 8000
        )
        Write-Host "Stopping FastAPI server on port $Port..."
        $command = "python $pythonScriptPath --command stop --port $Port"
       Invoke-PythonScript -Command $command -Description "Stop server on port $Port"
        Write-Host "Server stopped successfully."
    }

    # Функция для остановки всех серверов
    function Stop-AllFastAPIServers {
        Write-Host "Stopping all FastAPI servers..."
        $command = "python $pythonScriptPath --command stop_all"
        Invoke-PythonScript -Command $command -Description "Stop all servers"
        Write-Host "All servers stopped successfully."
    }

    # Функция для получения статуса сервера
    function Get-FastAPIServerStatus {
        Write-Host "Getting FastAPI server status..."
        $command = "python $pythonScriptPath --command status"
        Invoke-PythonScript -Command $command -Description "Get server status"
    }

    # Функция для проверки, запущен ли сервер на указанном порту
    function Test-PortIsListening {
        param (
            [int]$Port
        )
        try {
            Test-NetConnection -ComputerName localhost -Port $Port -ErrorAction Stop | Out-Null
            return $true
        }
        catch {
            return $false
        }
    }

   # Меню для выбора действий
    function Show-Menu {
        Write-Host "FastAPI Server Manager"
        Write-Host "----------------------"
        Write-Host "1. Start Server"
        Write-Host "2. Stop Server"
        Write-Host "3. Stop All Servers"
        Write-Host "4. Get Server Status"
        Write-Host "5. Exit"
    }


    # Главный цикл скрипта
    while ($true) {
         Show-Menu
        $choice = Read-Host "Enter your choice (1-5)"

        switch ($choice) {
            "1" {
                $port = Read-Host "Enter port number (default 8000)"
                if (-not $port) {
                    $port = 8000
                }  elseif ($port -notmatch '^\d+$') {
                     Write-Host "Invalid port number"
                     continue
                 }
                $serverHost = Read-Host "Enter host address (default 0.0.0.0)"
                if (-not $serverHost) {
                    $serverHost = "0.0.0.0"
                }

                if (Test-PortIsListening -Port $port) {
                    Write-Host "Server already running on port $port."
                }
                else {
                    Start-FastAPIServer -Port $port -serverHost $serverHost
                }
            }
            "2" {
               $port = Read-Host "Enter port number to stop"
                 if (-not $port) {
                   Write-Host "Port number is required"
                  }  elseif ($port -notmatch '^\d+$') {
                     Write-Host "Invalid port number"
                    continue
                 }else {
                   Stop-FastAPIServer -Port $port
                }
            }
            "3" {
                Stop-AllFastAPIServers
            }
             "4" {
                Get-FastAPIServerStatus
            }
            "5" {
                Write-Host "Exiting..."
                break
            }
            default {
                Write-Host "Invalid choice. Please try again."
            }
        }
        Write-Host ""
    }

}
finally {
    # Гарантированное освобождение мьютекса
    if ($mutex -ne $null) {
        if ($acquiredMutex) {
            $mutex.ReleaseMutex()
        }
        $mutex.Close()
    }
}