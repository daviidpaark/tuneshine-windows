Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

PythonPath = ScriptDir & "\.venv\Scripts\pythonw.exe"
MainScript = ScriptDir & "\main.py"

WshShell.CurrentDirectory = ScriptDir
WshShell.Run """" & PythonPath & """ """ & MainScript & """", 0, False
