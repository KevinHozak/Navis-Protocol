Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set objEnv = WshShell.Environment("PROCESS")

' Determine repository root
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
If fso.FolderExists(fso.BuildPath(strScriptDir, "backend")) Then
    rootDir = strScriptDir
Else
    rootDir = "C:\Projects\Navis-Protocol"
End If

backendDir = fso.BuildPath(rootDir, "backend")
frontendDir = fso.BuildPath(rootDir, "frontend")

' Resolve Python runtime
pythonExe = ""
If objEnv("NAVIS_PYTHON") <> "" Then
    If fso.FileExists(objEnv("NAVIS_PYTHON")) Then
        pythonExe = objEnv("NAVIS_PYTHON")
    End If
End If

If pythonExe = "" Then
    venvPython = fso.BuildPath(backendDir, ".venv\Scripts\python.exe")
    If fso.FileExists(venvPython) Then
        pythonExe = venvPython
    Else
        pythonExe = "python.exe"
    End If
End If

' Configure NAVIS_ROOT
If objEnv("NAVIS_ROOT") = "" Then
    objEnv("NAVIS_ROOT") = "G:\My Drive\Navis-Vault"
End If
objEnv("GEMINI_API_KEY") = objEnv("GEMINI_API_KEY")

backendCmd = """" & pythonExe & """ -m uvicorn main:app --host 127.0.0.1 --port 8000"
frontendCmd = "cmd.exe /c npm run dev"

If objEnv("NAVIS_LAUNCH_DRY_RUN") <> "" Then
    WScript.Echo "DRY_RUN: ROOT_DIR=" & rootDir
    WScript.Echo "DRY_RUN: BACKEND_DIR=" & backendDir
    WScript.Echo "DRY_RUN: FRONTEND_DIR=" & frontendDir
    WScript.Echo "DRY_RUN: NAVIS_ROOT=" & objEnv("NAVIS_ROOT")
    WScript.Echo "DRY_RUN: PYTHON_EXE=" & pythonExe
    WScript.Echo "DRY_RUN: BACKEND_CMD=" & backendCmd
    WScript.Echo "DRY_RUN: FRONTEND_CMD=" & frontendCmd
    WScript.Quit 0
End If

' 1. Start Backend (run hidden)
WshShell.CurrentDirectory = backendDir
WshShell.Run backendCmd, 0, False

' 2. Start Frontend (run hidden)
WshShell.CurrentDirectory = frontendDir
WshShell.Run frontendCmd, 0, False