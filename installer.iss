; Script de instalador Inno Setup para Jarvis AI
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

#define MyAppName "Jarvis AI"
#define MyAppPublisher "Jhonata"
#define MyAppURL "https://github.com/jhonata192/jarvis-ai"
#define MyAppExeName "JarvisAI.exe"

[Setup]
; Identificador único do aplicativo (gerado para o Jarvis AI)
AppId={{D37E84B1-18F2-4D93-94A5-63F09C114F23}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=dist-installer
OutputBaseFilename=JarvisAI-{#MyAppVersion}-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Iniciar o Jarvis AI automaticamente com o Windows"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
; Inclui todos os arquivos da compilação do PyInstaller
Source: "dist\JarvisAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startupicon

[Run]
Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Filename: "{app}\{#MyAppExeName}"; Flags: nowait postinstall skipifsilent
