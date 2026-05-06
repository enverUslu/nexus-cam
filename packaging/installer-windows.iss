#define MyAppName "Nexus.cam"
#define MyAppExeName "NexusCam.exe"
#define MyAppVersion "0.1.0"
#define RepoRoot SourcePath + "\.."

[Setup]
AppId={{C9E05F17-8F1B-4D23-9324-7C9DAF163D20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\NexusCam
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir={#RepoRoot}\dist\installer
OutputBaseFilename=NexusCam-Setup-v{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#RepoRoot}\dist\NexusCam\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
