#ifndef AppVersion
  #error Pass the application version with /DAppVersion.
#endif
#ifndef SourceDir
  #error Pass the absolute PyInstaller bundle directory with /DSourceDir.
#endif
#ifndef OutputDir
  #error Pass the absolute installer output directory with /DOutputDir.
#endif

[Setup]
AppId=Icescopy
AppName=Icescopy
AppVersion={#AppVersion}
AppPublisher=Bo Chen
AppPublisherURL=https://github.com/bochens/Icescopy
DefaultDirName={localappdata}\Programs\Icescopy
DefaultGroupName=Icescopy
DisableProgramGroupPage=no
AllowNoIcons=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
OutputDir={#OutputDir}
OutputBaseFilename=Icescopy-windows-installer
SetupIconFile={#SourceDir}\_internal\resources\app_icons\IcescopyApp.ico
UninstallDisplayIcon={app}\Icescopy.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Icescopy"; Filename: "{app}\Icescopy.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Icescopy.exe"
Name: "{userdesktop}\Icescopy"; Filename: "{app}\Icescopy.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Icescopy.exe"; Tasks: desktopicon

[InstallDelete]
; Old bundles could include Poppler's ICU78 DLL, which breaks Qt's Windows ICU API.
; Remove only these known obsolete files from a recognizable Icescopy install.
Type: files; Name: "{app}\_internal\icuuc.dll"; Check: IsExistingIcescopyInstallation
Type: files; Name: "{app}\_internal\icudt78.dll"; Check: IsExistingIcescopyInstallation

[Code]
function IsExistingIcescopyInstallation: Boolean;
begin
  Result := FileExists(ExpandConstant('{app}\Icescopy.exe')) and
    FileExists(ExpandConstant('{app}\_internal\PySide6\Qt6Core.dll'));
end;
