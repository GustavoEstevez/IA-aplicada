#define ProductName "VigiWork Cliente"
#define ProductId "{{2E6B3E0E-760B-4E46-A17F-A4758134C9BF}"
#define ProductVersion "1.0.5"
#define SourceRoot ".."

[Setup]
AppId={#ProductId}
AppName={#ProductName}
AppVersion={#ProductVersion}
AppPublisher=VigiWork
DefaultDirName={localappdata}\Programs\VigiWork\Cliente
DefaultGroupName=VigiWork Cliente
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
OutputDir=.
OutputBaseFilename=VigiWork-Cliente-Setup
Compression=lzma2/ultra64
SolidCompression=yes
UninstallDisplayName={#ProductName}
UninstallFilesDir={app}\Uninstall
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"; Flags: checkedonce

[Files]
Source: "{#SourceRoot}\client\*"; DestDir: "{app}\client"; Excludes: ".venv\*,__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\shared\*"; DestDir: "{app}\shared"; Excludes: "__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Preparar-Aplicacion.ps1"; DestDir: "{app}\setup"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\VigiWork Cliente"; Filename: "{app}\client\.venv\Scripts\pythonw.exe"; Parameters: """{app}\client\app.py"""; WorkingDir: "{app}\client"
Name: "{autodesktop}\VigiWork Cliente"; Filename: "{app}\client\.venv\Scripts\pythonw.exe"; Parameters: """{app}\client\app.py"""; WorkingDir: "{app}\client"; Tasks: desktopicon

[Run]
Filename: "{app}\client\.venv\Scripts\pythonw.exe"; Parameters: """{app}\client\app.py"""; WorkingDir: "{app}\client"; Description: "Abrir VigiWork Cliente"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\client\.venv"
Type: filesandordirs; Name: "{app}\setup"

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params: String;
  LogPath: String;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Preparando Python y dependencias. Esto puede tardar unos minutos...';
    WizardForm.ProgressGauge.Style := npbstMarquee;
    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\setup\Preparar-Aplicacion.ps1') + '" -Tipo Cliente -Directorio "' + ExpandConstant('{app}') + '"';
    if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
    if ResultCode <> 0 then
    begin
      LogPath := ExpandConstant('{localappdata}\VigiWork\Logs\instalacion-Cliente.log');
      MsgBox('No se pudo completar la preparación de la aplicación. Abrí el registro para ver el error exacto:' + #13#10 + LogPath, mbError, MB_OK);
      Abort;
    end;
  end;
end;
