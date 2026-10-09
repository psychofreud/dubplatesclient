; Dubplates.net Client: Windows installer (Inno Setup 6). Built by installer\build_windows.ps1 (it passes AppVersion and Src).
; Per-user install: no admin rights. The stem engine (PyTorch) is downloaded on first start.

#define AppName "Dubplates.net Client"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef Src
  #define Src "..\build\win"
#endif

[Setup]
AppId={{6A1F4E52-9C3D-4B7A-8E21-D0B1A7C5F3E9}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=dubplates.net
AppPublisherURL=https://dubplates.net
AppSupportURL=https://github.com/psychofreud/dubplatesclient
DefaultDirName={localappdata}\Programs\Dubplates Client
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\build
OutputBaseFilename=DubplatesClient-Setup-{#AppVersion}
SetupIconFile=..\dubplates_client\assets\icon.ico
UninstallDisplayIcon={app}\app\dubplates_client\assets\icon.ico
UninstallDisplayName={#AppName}
LicenseFile=..\LICENSE
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
; tell Windows that the dubplates:// link type changed (else Explorer / browsers may not see it until a sign-out)
ChangesAssociations=yes

[Tasks]
Name: "desktopicon"; Description: "Make a desktop icon"; GroupDescription: "Icons:"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m dubplates_client.main"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\dubplates_client\assets\icon.ico"; AppUserModelID: "net.dubplates.client"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m dubplates_client.main"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\dubplates_client\assets\icon.ico"; AppUserModelID: "net.dubplates.client"; Tasks: desktopicon

[Registry]
; dubplates:// links (from dubplates.net: "Make stems") open the client. Per user, removed on uninstall.
Root: HKCU; Subkey: "Software\Classes\dubplates"; ValueType: string; ValueName: ""; ValueData: "URL:Dubplates.net Client"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\dubplates"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\dubplates\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\app\dubplates_client\assets\icon.ico"""
Root: HKCU; Subkey: "Software\Classes\dubplates\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\python\pythonw.exe"" -m dubplates_client.main ""%1"""

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m dubplates_client.main"; WorkingDir: "{app}\app"; Description: "Start {#AppName}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; the engine (PyTorch etc.) was installed into {app}\python on first start: remove it too.
; Settings and downloaded models stay in %APPDATA%\Dubplates Client (models are big; a new install uses them again).
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\app"
