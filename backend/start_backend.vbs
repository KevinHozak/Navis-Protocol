Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set objEnv = WshShell.Environment("PROCESS")

' Determine backend directory
strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
If fso.FileExists(fso.BuildPath(strScriptDir, "main.py")) Then
    backendDir = strScriptDir
Else
    backendDir = "C:\Projects\Navis-Protocol\backend"
End If

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

' Resolve NAVIS_ROOT
If objEnv("NAVIS_ROOT") = "" Then
    objEnv("NAVIS_ROOT") = "G:\My Drive\Navis-Vault"
End If

backendCmd = """" & pythonExe & """ -m uvicorn main:app --host 127.0.0.1 --port 8000"

If objEnv("NAVIS_LAUNCH_DRY_RUN") <> "" Then
    WScript.Echo "DRY_RUN: BACKEND_DIR=" & backendDir
    WScript.Echo "DRY_RUN: NAVIS_ROOT=" & objEnv("NAVIS_ROOT")
    WScript.Echo "DRY_RUN: PYTHON_EXE=" & pythonExe
    WScript.Echo "DRY_RUN: BACKEND_CMD=" & backendCmd
    WScript.Quit 0
End If

WshShell.CurrentDirectory = backendDir
WshShell.Run backendCmd, 0, False