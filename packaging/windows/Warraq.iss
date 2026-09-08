#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

#ifndef SourceDir
  #define SourceDir "..\..\dist\windows\app"
#endif

#ifndef OutputDir
  #define OutputDir "..\..\dist\windows\installer"
#endif

[Setup]
AppId={{EE07122C-534E-478F-BA57-9ACD25759B8B}
AppName=Warraq
AppVersion={#AppVersion}
AppVerName=Warraq {#AppVersion}
AppPublisher=Warraq
DefaultDirName={autopf}\Warraq
DefaultGroupName=Warraq
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no
SetupIconFile=..\..\waraq\assets\Warraq.ico
UninstallDisplayIcon={app}\Warraq.exe
OutputDir={#OutputDir}
OutputBaseFilename=Warraq-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Warraq"; Filename: "{app}\Warraq.exe"
Name: "{autodesktop}\Warraq"; Filename: "{app}\Warraq.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Warraq.exe"; Description: "Launch Warraq"; Flags: nowait postinstall skipifsilent

; User data lives in %LOCALAPPDATA%\Warraq. No installer or uninstaller
; directive targets that directory, so upgrades and uninstall preserve it.
