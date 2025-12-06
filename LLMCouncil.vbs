' LLM Council - VBScript Launcher (completely hidden, no console flash)
' Double-click this file for a fully silent start

Set objShell = CreateObject("WScript.Shell")
strPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
objShell.CurrentDirectory = strPath
objShell.Run "powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & strPath & "\LLMCouncil-Tray.ps1""", 0, False
