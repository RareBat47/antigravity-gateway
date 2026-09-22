' Arena Gateway Background Service Launcher (Hidden Window)
Option Explicit
Dim WshShell, fso, target
Set fso = CreateObject("Scripting.FileSystemObject")
target = "D:\arena-gateway-workspace\start_service.bat"

If fso.FileExists(target) Then
    Set WshShell = CreateObject("WScript.Shell")
    ' 0 = vbHide (runs silently in the background without command window)
    WshShell.Run Chr(34) & target & Chr(34), 0, False
End If
