#define ProductName "VigiWork Servidor"
#define ProductId "{{A9B152B1-19F2-48B4-9374-0B9DE1332431}"
#define ProductVersion "1.0.5"
#define SourceRoot ".."

[Setup]
AppId={#ProductId}
AppName={#ProductName}
AppVersion={#ProductVersion}
AppPublisher=VigiWork
DefaultDirName={localappdata}\Programs\VigiWork\Servidor
DefaultGroupName=VigiWork Servidor
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
OutputDir=.
OutputBaseFilename=VigiWork-Servidor-Setup
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
Source: "{#SourceRoot}\server\*"; DestDir: "{app}\server"; Excludes: ".venv\*,__pycache__\*,*.pyc,models\*,tools\*,cameras.json,access_key.txt"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#SourceRoot}\shared\*"; DestDir: "{app}\shared"; Excludes: "__pycache__\*,*.pyc"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Preparar-Aplicacion.ps1"; DestDir: "{app}\setup"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\VigiWork Servidor"; Filename: "{app}\server\.venv\Scripts\pythonw.exe"; Parameters: """{app}\server\app.py"""; WorkingDir: "{app}\server"
Name: "{autodesktop}\VigiWork Servidor"; Filename: "{app}\server\.venv\Scripts\pythonw.exe"; Parameters: """{app}\server\app.py"""; WorkingDir: "{app}\server"; Tasks: desktopicon

[Run]
Filename: "{app}\server\.venv\Scripts\pythonw.exe"; Parameters: """{app}\server\app.py"""; WorkingDir: "{app}\server"; Description: "Abrir VigiWork Servidor"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\server\.venv"
Type: filesandordirs; Name: "{app}\server\models"
Type: filesandordirs; Name: "{app}\server\tools"
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
    WizardForm.StatusLabel.Caption := 'Preparando Python, dependencias y detector. Esto puede tardar unos minutos...';
    WizardForm.ProgressGauge.Style := npbstMarquee;
    Params := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\setup\Preparar-Aplicacion.ps1') + '" -Tipo Servidor -Directorio "' + ExpandConstant('{app}') + '"';
    if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'), Params, ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
    if ResultCode <> 0 then
    begin
      LogPath := ExpandConstant('{localappdata}\VigiWork\Logs\instalacion-Servidor.log');
      MsgBox('No se pudo completar la preparación de la aplicación. Abrí el registro para ver el error exacto:' + #13#10 + LogPath, mbError, MB_OK);
      Abort;
    end;
  end;
end;
