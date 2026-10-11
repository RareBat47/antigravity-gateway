Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

scriptPath = WScript.ScriptFullName
scriptFolder = fso.GetParentFolderName(scriptPath)
projectFolder = fso.GetParentFolderName(scriptFolder)

pythonw = projectFolder & "\.venv\Scripts\pythonw.exe"
If Not fso.FileExists(pythonw) Then
    pythonw = "pythonw.exe"
End If

WshShell.CurrentDirectory = projectFolder
WshShell.Run """" & pythonw & """ -m agw.main", 0, False
