#NoEnv  ; Recommended for performance and compatibility with future AutoHotkey releases.
; #Warn  ; Enable warnings to assist with detecting common errors.
SendMode Input  ; Recommended for new scripts due to its superior speed and reliability.
SetWorkingDir %A_ScriptDir%  ; Ensures a consistent starting directory.
#Include TF.ahk

mayaDir = %A_MyDocuments%\maya
if (FileExist(mayaDir) = "") {
	OnMessage(0x44, "OnMsgBoxA")
	MsgBox 0x80, Maya Directory Not Found, No maya directory found in %A_MyDocuments%. Install will now terminate.
	OnMessage(0x44, "")

	OnMsgBoxA() {
		DetectHiddenWindows, On
		Process, Exist
		If (WinExist("ahk_class #32770 ahk_pid " . ErrorLevel)) {
			hIcon := LoadPicture("imageres.dll", "w32 Icon94", _)
			SendMessage 0x172, 1, %hIcon% , Static1 ;STM_SETIMAGE
		}
	}
	ExitApp
}

validYear := False
while (validYear = False) {
	FileSelectFolder, installDir, %mayaDir%, 2, Select year to install to:
	SplitPath, installDir, year


	; TODO: validate that this folder name is a year
	yearPos := RegExMatch(year, "^(19|20)\d{2}$")
	if (yearPos > 0) {
		validYear := True
	} else {
		validYear := False
		OnMessage(0x44, "OnMsgBoxB")
		MsgBox 0x85, Invalid Folder, Invalid Maya install folder. Please choose a folder containing a year name (e.g. "/maya/2017/")
		OnMessage(0x44, "")

		IfMsgBox Retry, {
			; Keep validYear false
		} Else IfMsgBox Cancel, {
			ExitApp
		}

		OnMsgBoxB() {
			DetectHiddenWindows, On
			Process, Exist
			If (WinExist("ahk_class #32770 ahk_pid " . ErrorLevel)) {
				hIcon := LoadPicture("imageres.dll", "w32 Icon80", _)
				SendMessage 0x172, 1, %hIcon% , Static1 ;STM_SETIMAGE
			}
		}
	}
}

localPluginDir = %A_ScriptDir%\plugin
if (FileExist(localPluginDir) = "") {
	OnMessage(0x44, "OnMsgBoxC")
	MsgBox 0x80, Plugin Directory Not Found, No plugin directory found in %A_ScriptDir%. Install will now terminate.
	OnMessage(0x44, "")

	OnMsgBoxC() {
		DetectHiddenWindows, On
		Process, Exist
		If (WinExist("ahk_class #32770 ahk_pid " . ErrorLevel)) {
			hIcon := LoadPicture("imageres.dll", "w32 Icon94", _)
			SendMessage 0x172, 1, %hIcon% , Static1 ;STM_SETIMAGE
		}
	}
	ExitApp
}

installPluginDir = %installDir%\plugin
FileCopyDir, %localPluginDir%, %installPluginDir%, 1
if (ErrorLevel) {
	OnMessage(0x44, "OnMsgBoxD")
	MsgBox 0x80, Plugin Directory Error, Could not copy %localPluginDir% to %installPluginDir%. Install will now terminate.
	OnMessage(0x44, "")

	OnMsgBoxD() {
		DetectHiddenWindows, On
		Process, Exist
		If (WinExist("ahk_class #32770 ahk_pid " . ErrorLevel)) {
			hIcon := LoadPicture("imageres.dll", "w32 Icon94", _)
			SendMessage 0x172, 1, %hIcon% , Static1 ;STM_SETIMAGE
		}
	}
	ExitApp
}

; TODO: edit Maya.env or Env Var to add plugin path
mayaENVPath = %installDir%\Maya.env

pluginEditType = -1
pluginLine = 0
templateEditType = -1
templateLine = 0'
Loop, Read, %mayaENVPath%
{
	if (pluginEditType > -1 && templateEditType > -1) {
		; Both necessary lines have been found, terminate early
		break
	}
	
	if (pluginEditType = -1 && SubStr(A_LoopReadLine, 1, 17) = "MAYA_PLUG_IN_PATH") {
		if (InStr(A_LoopReadLine, installPluginDir, , 17) > 0) {
			; Dir already present
			pluginEditType = 0
		} else {
			if (RegExMatch(A_LoopReadLine, "\s*=\s*$", , 18) > 0) {
				; MAYA_PLUG_IN_PATH = 
				pluginEditType = 2
			} else {
				if (InStr(A_LoopReadLine, "=", , 18) = 0) {
					; MAYA_PLUG_IN_PATH
					pluginEditType = 1
				} else {
					; MAYA_PLUG_IN_PATH = ...
					pluginEditType = 3
				}
			}
		}
		pluginLine := A_Index
	}
	if (templateEditType = -1 && SubStr(A_LoopReadLine, 1, 25) = "MAYA_CUSTOM_TEMPLATE_PATH") {
		if (InStr(A_LoopReadLine, installPluginDir, , 25) > 0) {
			; Install done
			templateEditType = 0
		} else {
			if (RegExMatch(A_LoopReadLine, "\s*=\s*$", , 26) > 0) {
				; MAYA_CUSTOM_TEMPLATE_PATH = 
				templateEditType = 2
			} else {
				if (InStr(A_LoopReadLine, "=", , 26) = 0) {
					; MAYA_CUSTOM_TEMPLATE_PATH
					templateEditType = 1
				} else {
					; MAYA_CUSTOM_TEMPLATE_PATH = ...
					templateEditType = 3
				}
			}
		}
		templateLine := A_Index
	}
}

if (pluginEditType = -1) {
	FileAppend, `nMAYA_PLUG_IN_PATH = %installPluginDir%, %mayaENVPath%, UTF-8
} else if (pluginEditType = 0) {
	; Dir already present, do nothing
} else if (pluginEditType = 1) {
	TF_InsertSuffix("!" . mayaENVPath, pluginLine, pluginLine, " = " . installPluginDir)
} else if (pluginEditType = 2) {
	TF_InsertSuffix("!" . mayaENVPath, pluginLine, pluginLine, installPluginDir)
} else if (pluginEditType = 3) {
	TF_InsertSuffix("!" . mayaENVPath, pluginLine, pluginLine, ";" . installPluginDir)
} else {
	throw Exception("Invalid pluginEditType (" . pluginEditType . "). Contact Jake to fix this.")
	ExitApp
}

if (templateEditType = -1) {
	FileAppend, `nMAYA_CUSTOM_TEMPLATE_PATH = %installPluginDir%, %mayaENVPath%, UTF-8
} else if (templateEditType = 0) {
	; Dir already present, do nothing
} else if (templateEditType = 1) {
	TF_InsertSuffix("!" . mayaENVPath, templateLine, templateLine, " = " . installPluginDir)
} else if (templateEditType = 2) {
	TF_InsertSuffix("!" . mayaENVPath, templateLine, templateLine, installPluginDir)
} else if (templateEditType = 3) {
	TF_InsertSuffix("!" . mayaENVPath, templateLine, templateLine, ";" . installPluginDir)
} else {
	throw Exception("Invalid templateEditType (" . templateEditType . "). Contact Jake to fix this.")
	ExitApp
}

OnMessage(0x44, "OnMsgBoxE")
MsgBox 0x80, Installation Successful, Installation completed successfully! Remember to enable "AccelMotionCurve.py" Auto-Load in Maya's Plugin Manager.
OnMessage(0x44, "")

OnMsgBoxE() {
    DetectHiddenWindows, On
    Process, Exist
    If (WinExist("ahk_class #32770 ahk_pid " . ErrorLevel)) {
        hIcon := LoadPicture("imageres.dll", "w32 Icon228", _)
        SendMessage 0x172, 1, %hIcon% , Static1 ;STM_SETIMAGE
    }
}
ExitApp
