<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="de_DE">
<context>
    <name>ErrorService</name>
    <message>
        <location filename="../services/error_service.py" line="84"/>
        <source>Save</source>
        <translation>Speichern</translation>
    </message>
    <message>
        <location filename="../services/error_service.py" line="88"/>
        <source>Discard</source>
        <translation>Verwerfen</translation>
    </message>
    <message>
        <location filename="../services/error_service.py" line="92"/>
        <source>Cancel</source>
        <translation>Abbrechen</translation>
    </message>
    <message>
        <location filename="../commands/registry.py" line="63"/>
        <source>Error</source>
        <translation>Fehler</translation>
    </message>
    <message>
        <location filename="../commands/registry.py" line="65"/>
        <source>The command &apos;{title}&apos; could not be executed.</source>
        <translation>Der Befehl „{title}“ konnte nicht ausgeführt werden.</translation>
    </message>
</context>
<context>
    <name>ExportController</name>
    <message>
        <location filename="../controllers/export_controller.py" line="49"/>
        <source>Export unavailable</source>
        <translation>Export nicht möglich</translation>
    </message>
</context>
<context>
    <name>ExportDialog</name>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="102"/>
        <source>Export video</source>
        <translation>Video exportieren</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="103"/>
        <source>Output file</source>
        <translation>Ausgabedatei</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="104"/>
        <source>Quality</source>
        <translation>Qualität</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="105"/>
        <source>Browse…</source>
        <translation>Durchsuchen…</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="106"/>
        <source>Cancel</source>
        <translation>Abbrechen</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="107"/>
        <source>Export</source>
        <translation>Exportieren</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="108"/>
        <source>Ready to export.</source>
        <translation>Bereit zum Export.</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="109"/>
        <source>High</source>
        <translation>Hoch</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="110"/>
        <source>Standard</source>
        <translation>Standard</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="124"/>
        <location filename="../views/dialogs/export_dialog.py" line="133"/>
        <location filename="../views/dialogs/export_dialog.py" line="142"/>
        <source>Export unavailable</source>
        <translation>Export nicht möglich</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="143"/>
        <source>Please choose an output file.</source>
        <translation>Bitte wähle eine Ausgabedatei.</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="163"/>
        <location filename="../views/dialogs/export_dialog.py" line="178"/>
        <location filename="../views/dialogs/export_dialog.py" line="209"/>
        <source>Preparing stars…</source>
        <translation>Sterne werden vorbereitet…</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="125"/>
        <source>An export is already running.</source>
        <translation>Es läuft bereits ein Export.</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="192"/>
        <source>Rendering frames… {current} of {total}</source>
        <translation>Frames werden gerendert… {current} von {total}</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="212"/>
        <source>Rendering frames…</source>
        <translation>Frames werden gerendert…</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="217"/>
        <source>Export completed.</source>
        <translation>Export abgeschlossen.</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="220"/>
        <source>Export successful</source>
        <translation>Export erfolgreich</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="221"/>
        <source>Video saved to:
{path}</source>
        <translation>Video gespeichert unter:
{path}</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="229"/>
        <source>Export cancelled.</source>
        <translation>Export abgebrochen.</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="233"/>
        <source>Export failed</source>
        <translation>Export fehlgeschlagen</translation>
    </message>
    <message>
        <location filename="../views/dialogs/export_dialog.py" line="251"/>
        <source>Cancelling export…</source>
        <translation>Export wird abgebrochen…</translation>
    </message>
</context>
<context>
    <name>ExportWorker</name>
    <message>
        <location filename="../core/exporter.py" line="276"/>
        <source>A rendered chunk has an invalid size ({actual_bytes} instead of {expected_bytes}).</source>
        <translation>Ein gerenderter Abschnitt hat eine ungültige Größe ({actual_bytes} statt {expected_bytes}).</translation>
    </message>
    <message>
        <location filename="../core/exporter.py" line="468"/>
        <source>Fade snapshots are missing for chunk starts: {starts}</source>
        <translation>Überblendungsstände fehlen für folgende Abschnittsanfänge: {starts}</translation>
    </message>
    <message>
        <location filename="../core/exporter.py" line="281"/>
        <location filename="../core/exporter.py" line="491"/>
        <source>FFmpeg could not be started.</source>
        <translation>FFmpeg konnte nicht gestartet werden.</translation>
    </message>
    <message>
        <location filename="../core/exporter.py" line="292"/>
        <location filename="../core/exporter.py" line="608"/>
        <source>FFmpeg error: {error}</source>
        <translation>FFmpeg-Fehler: {error}</translation>
    </message>
    <message>
        <location filename="../core/exporter.py" line="412"/>
        <source>FFmpeg was not found. Install FFmpeg and make sure it is available on PATH.</source>
        <translation type="unfinished">FFmpeg wurde nicht gefunden. Installiere FFmpeg und stell sicher, dass es über PATH verfügbar ist.</translation>
    </message>
    <message>
        <location filename="../core/exporter.py" line="609"/>
        <source>Unknown error</source>
        <translation>Unbekannter Fehler</translation>
    </message>
</context>
<context>
    <name>FocusPointsControl</name>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="178"/>
        <source>Start</source>
        <translation>Start</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="180"/>
        <source>Optional start look-at. When unset, the camera starts at the image center.</source>
        <translation>Optionaler Startpunkt. Wenn nicht gesetzt, startet die Kamera in der Bildmitte.</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="182"/>
        <source>Target</source>
        <translation>Ziel</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="184"/>
        <source>Optional end look-at. When unset, the camera ends at the image center.</source>
        <translation>Optionaler Zielpunkt. Wenn nicht gesetzt, endet die Kamera in der Bildmitte.</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="221"/>
        <source>No image loaded</source>
        <translation>Kein Bild geladen</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="225"/>
        <source>No path set · camera stays centered</source>
        <translation>Kein Pfad gesetzt · Kamera bleibt zentriert</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="231"/>
        <source>Start {x} · {y}</source>
        <translation>Start {x} · {y}</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="237"/>
        <source>Start: center</source>
        <translation>Start: Mitte</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="241"/>
        <source>Target {x} · {y}</source>
        <translation>Ziel {x} · {y}</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="247"/>
        <source>Target: center</source>
        <translation>Ziel: Mitte</translation>
    </message>
</context>
<context>
    <name>ImageError</name>
    <message>
        <location filename="../utils/image.py" line="36"/>
        <source>Image could not be loaded: {path}</source>
        <translation>Bild konnte nicht geladen werden: {path}</translation>
    </message>
</context>
<context>
    <name>ImageOpenDialog</name>
    <message>
        <location filename="../views/dialogs/image_open_dialog.py" line="34"/>
        <source>Load image</source>
        <translation>Bild laden</translation>
    </message>
    <message>
        <location filename="../views/dialogs/image_open_dialog.py" line="36"/>
        <source>Images (*.jpg *.jpeg *.png *.tif *.tiff);;All files (*)</source>
        <translation>Bilder (*.jpg *.jpeg *.png *.tif *.tiff);;Alle Dateien (*)</translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../views/main_window.py" line="107"/>
        <location filename="../views/main_window.py" line="147"/>
        <source>Open Recent</source>
        <translation>Zuletzt geöffnet</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="151"/>
        <source>No Recent Projects</source>
        <translation>Keine zuletzt geöffneten Projekte</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="249"/>
        <source>Ready</source>
        <translation>Bereit</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="268"/>
        <source>New</source>
        <translation>Neu</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="269"/>
        <source>Open…</source>
        <translation>Öffnen…</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="270"/>
        <source>Save</source>
        <translation>Speichern</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="271"/>
        <source>Save as…</source>
        <translation>Speichern unter…</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="273"/>
        <source>Load image…</source>
        <translation>Bild laden…</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="274"/>
        <source>Export video…</source>
        <translation>Video exportieren…</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="275"/>
        <source>Settings…</source>
        <translation>Einstellungen…</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="311"/>
        <source>Project</source>
        <translation>Projekt</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="312"/>
        <source>Settings</source>
        <translation>Einstellungen</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="272"/>
        <source>Quit</source>
        <translation>Beenden</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="310"/>
        <source>File</source>
        <translation>Datei</translation>
    </message>
    <message>
        <location filename="../views/main_window.py" line="423"/>
        <location filename="../views/main_window.py" line="433"/>
        <source>Project saved: {path}</source>
        <translation>Projekt gespeichert: {path}</translation>
    </message>
</context>
<context>
    <name>PreviewPanel</name>
    <message>
        <location filename="../views/widgets/preview_panel.py" line="103"/>
        <source>Load at least one image to see the preview.</source>
        <translation>Lade mindestens ein Bild, um die Vorschau zu sehen.</translation>
    </message>
</context>
<context>
    <name>ProjectController</name>
    <message>
        <location filename="../controllers/project_controller.py" line="38"/>
        <location filename="../controllers/project_controller.py" line="111"/>
        <source>Untitled Project</source>
        <translation>Unbenanntes Projekt</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="99"/>
        <source>Unsaved changes</source>
        <translation>Ungespeicherte Änderungen</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="100"/>
        <source>Do you want to save your changes?</source>
        <translation>Möchtest du deine Änderungen speichern?</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="150"/>
        <location filename="../controllers/project_controller.py" line="160"/>
        <source>Could not open project</source>
        <translation>Projekt konnte nicht geladen werden</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="151"/>
        <source>The project file no longer exists:
{path}</source>
        <translation>Die Projektdatei existiert nicht mehr:
{path}</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="212"/>
        <location filename="../controllers/project_controller.py" line="220"/>
        <source>Save failed</source>
        <translation>Speichern fehlgeschlagen</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="221"/>
        <source>Unexpected error while saving: {error}</source>
        <translation>Unerwarteter Fehler beim Speichern: {error}</translation>
    </message>
    <message>
        <location filename="../controllers/project_controller.py" line="249"/>
        <source>Could not load image</source>
        <translation>Bild konnte nicht geladen werden</translation>
    </message>
</context>
<context>
    <name>ProjectError</name>
    <message>
        <location filename="../core/project.py" line="21"/>
        <source>Project could not be saved: {error}</source>
        <translation>Das Projekt konnte nicht gespeichert werden: {error}</translation>
    </message>
    <message>
        <location filename="../core/project.py" line="24"/>
        <source>Project data could not be serialized: {error}</source>
        <translation>Die Projektdaten konnten nicht serialisiert werden: {error}</translation>
    </message>
    <message>
        <location filename="../core/project.py" line="27"/>
        <source>Project file not found: {path}</source>
        <translation>Projektdatei nicht gefunden: {path}</translation>
    </message>
    <message>
        <location filename="../core/project.py" line="30"/>
        <source>The project file does not contain valid JSON.</source>
        <translation>Die Projektdatei enthält kein gültiges JSON.</translation>
    </message>
    <message>
        <location filename="../core/project.py" line="33"/>
        <source>The project file has an invalid format.</source>
        <translation>Die Projektdatei hat ein ungültiges Format.</translation>
    </message>
</context>
<context>
    <name>ProjectOpenDialog</name>
    <message>
        <location filename="../views/dialogs/project_open_dialog.py" line="35"/>
        <source>Open project</source>
        <translation>Projekt öffnen</translation>
    </message>
    <message>
        <location filename="../views/dialogs/project_open_dialog.py" line="37"/>
        <source>Starflight project (*.sf);;All files (*)</source>
        <translation>Starflight-Projekt (*.sf);;Alle Dateien (*)</translation>
    </message>
</context>
<context>
    <name>ProjectSaveDialog</name>
    <message>
        <location filename="../views/dialogs/project_save_dialog.py" line="15"/>
        <source>Save project</source>
        <translation>Projekt speichern</translation>
    </message>
    <message>
        <location filename="../views/dialogs/project_save_dialog.py" line="19"/>
        <source>Starflight project (*.sf);;All files (*)</source>
        <translation>Starflight-Projekt (*.sf);;Alle Dateien (*)</translation>
    </message>
    <message>
        <location filename="../views/dialogs/project_save_dialog.py" line="22"/>
        <source>Save</source>
        <translation>Speichern</translation>
    </message>
    <message>
        <location filename="../views/dialogs/project_save_dialog.py" line="23"/>
        <source>Cancel</source>
        <translation>Abbrechen</translation>
    </message>
</context>
<context>
    <name>SettingsDialog</name>
    <message>
        <location filename="__init__.py" line="61"/>
        <source>German</source>
        <translation>Deutsch</translation>
    </message>
    <message>
        <location filename="__init__.py" line="62"/>
        <source>English</source>
        <translation>Englisch</translation>
    </message>
    <message>
        <location filename="../views/dialogs/settings_dialog.py" line="65"/>
        <source>Settings</source>
        <translation>Einstellungen</translation>
    </message>
    <message>
        <location filename="../views/dialogs/settings_dialog.py" line="66"/>
        <source>Language</source>
        <translation>Sprache</translation>
    </message>
</context>
<context>
    <name>SettingsPanel</name>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="556"/>
        <source>Project &amp; Video</source>
        <translation>Projekt &amp; Video</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="557"/>
        <source>Background</source>
        <translation>Hintergrund</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="568"/>
        <source>Stars — Appearance</source>
        <translation>Sterne — Erscheinung</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="569"/>
        <source>Stars — Animation</source>
        <translation>Sterne — Animation</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="571"/>
        <source>Load image…</source>
        <translation>Bild laden…</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="572"/>
        <source>Image</source>
        <translation>Bild</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="575"/>
        <source>Photo used as the flying-through background. Load a PNG or TIFF without embedded stars.</source>
        <translation>Dein Bild als Hintergrund für den Flug. Lade ein PNG oder TIFF ohne eingebettete Sterne.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="579"/>
        <source>Target resolution</source>
        <translation>Zielauflösung</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="582"/>
        <source>Output size of the exported video. Higher values need more memory and take longer to export.</source>
        <translation>Ausgabegröße des exportierten Videos. Höhere Werte benötigen mehr Speicher und dauern länger beim Export.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="586"/>
        <location filename="../views/widgets/settings_panel.py" line="646"/>
        <location filename="../views/widgets/settings_panel.py" line="720"/>
        <source>Custom</source>
        <translation>Benutzerdefiniert</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="588"/>
        <source>Manual width and height in pixels when no preset fits your target.</source>
        <translation>Manuelle Breite und Höhe in Pixeln, wenn keine Voreinstellung zu deinem Ziel passt.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="590"/>
        <source>Width</source>
        <translation>Breite</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="591"/>
        <source>Height</source>
        <translation>Höhe</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="592"/>
        <source>Video length</source>
        <translation>Videolänge</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="594"/>
        <source>Total duration of the exported clip in seconds.</source>
        <translation>Gesamtdauer des exportierten Clips in Sekunden.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="596"/>
        <source>Frame rate</source>
        <translation>Bildrate</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="604"/>
        <location filename="../views/widgets/settings_panel.py" line="605"/>
        <location filename="../views/widgets/settings_panel.py" line="606"/>
        <source>{fps} fps</source>
        <translation>{fps} Bilder/s</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="608"/>
        <source>Image scale</source>
        <translation>Bildgröße</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="615"/>
        <source>Zoom in</source>
        <translation>Annäherung</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="619"/>
        <source>Rotation</source>
        <translation>Drehung</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="661"/>
        <source>Pixel size of the largest nearby stars. Higher values make bright stars stand out more clearly.</source>
        <translation>Pixelgröße der größten nahen Sterne. Höhere Werte lassen helle Sterne klarer hervortreten.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="665"/>
        <source>Size spread</source>
        <translation>Größenverteilung</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="668"/>
        <source>How many mid-sized and large stars appear. 0% keeps the compact default; higher values fill the field with more clearly larger stars.</source>
        <translation>Wie viele mittelgroße und große Sterne erscheinen. 0 % behält das kompakte Standardfeld; höhere Werte füllen das Feld mit deutlich größeren Sternen.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="678"/>
        <source>Spread</source>
        <translation>Verteilung</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="697"/>
        <source>How colorful stars look. 0% = white stars, higher = more spectral color. Large bright stars lean blue; mid-sized stars often stay yellow or white.</source>
        <translation>Wie farbig die Sterne wirken. 0 % = weiße Sterne, höher = mehr Spektralfarbe. Große helle Sterne tendieren zu Blau; mittlere bleiben oft gelb oder weiß.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="705"/>
        <source>Star motion over time, independent of video length. 1.0 matches the previous default feel of a 10s clip.</source>
        <translation>Sternbewegung über die Zeit, unabhängig von der Videolänge. 1,0 entspricht dem bisherigen Standardgefühl bei 10&#x202f;s.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="738"/>
        <source>1080 × 1920 (Portrait)</source>
        <translation>1080 × 1920 (Hochformat)</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="739"/>
        <source>1920 × 1080 (Landscape)</source>
        <translation>1920 × 1080 (Querformat)</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="740"/>
        <source>2160 × 3840 (4K Portrait)</source>
        <translation>2160 × 3840 (4K-Hochformat)</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="627"/>
        <source>Frame edges</source>
        <translation>Randbereiche</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="634"/>
        <source>Fill empty areas during motion</source>
        <translation>Leere Bereiche bei Bewegung ausfüllen</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="674"/>
        <location filename="../views/widgets/settings_panel.py" line="684"/>
        <source>Strength</source>
        <translation>Stärke</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="686"/>
        <source>Soft halo around bright stars. Set to 0% to turn glow off completely.</source>
        <translation>Weicher Halo um helle Sterne. Bei 0 % ist Leuchten komplett aus.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="688"/>
        <source>By depth</source>
        <translation>Nach Tiefe</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="690"/>
        <source>Extra glow for nearby stars. Enabled when Strength is above 0%.</source>
        <translation>Zusätzliches Leuchten für nahe Sterne. Nur bedienbar, wenn Stärke über 0 % liegt.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="693"/>
        <source>Color</source>
        <translation>Farbe</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="694"/>
        <source>Intensity</source>
        <translation>Intensität</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="680"/>
        <source>More realistic mix of faint and bright stars.</source>
        <translation>Realistischere Mischung aus schwachen und hellen Sternen.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="611"/>
        <source>Base size of the source image in the video. 100% fills the frame; smaller values shrink the image, larger values zoom in further.</source>
        <translation>Grundgröße des Quellbilds im Video. 100 % füllt den Rahmen; kleinere Werte verkleinern, größere zoomen weiter hinein.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="558"/>
        <source>Camera path</source>
        <translation>Kamerapfad</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="561"/>
        <source>Optional start and target points. Each point is the center of the video frame. Enable a point to show its marker, then drag it on the preview. Only a target starts from the image center; only a start ends at the image center.</source>
        <translation>Optionale Start- und Zielpunkte. Jeder Punkt ist die Mitte des Video-Ausschnitts. Aktiviere einen Punkt, um das Symbol zu sehen, und ziehe ihn dann in der Vorschau. Nur Ziel: Start in der Bildmitte. Nur Start: Ziel in der Bildmitte.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="567"/>
        <source>Stars — Count &amp; Size</source>
        <translation>Sterne — Anzahl &amp; Größe</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="630"/>
        <source>Automatically scales and shifts the image when needed so no black borders appear during focus and rotation.</source>
        <translation>Skaliert und verschiebt das Bild bei Bedarf automatisch, damit bei Fokus und Drehung keine schwarzen Ränder entstehen.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="636"/>
        <source>Density</source>
        <translation>Dichte</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="643"/>
        <source>Low</source>
        <translation>Wenig</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="644"/>
        <source>Medium</source>
        <translation>Mittel</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="645"/>
        <source>High</source>
        <translation>Viel</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="647"/>
        <source>Star count</source>
        <translation>Sternanzahl</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="649"/>
        <source>More stars create a denser field. Very high values can slow export.</source>
        <translation>Mehr Sterne ergeben ein dichteres Feld. Sehr hohe Werte können den Export verlangsamen.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="651"/>
        <source>Smallest stars</source>
        <translation>Kleinste Sterne</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="658"/>
        <source>Largest stars</source>
        <translation>Größte Sterne</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="673"/>
        <source>Brightness</source>
        <translation>Helligkeit</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="683"/>
        <source>Glow</source>
        <translation>Leuchten</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="599"/>
        <source>Frames per second. 24 feels cinematic, 30 is standard, 60 is very smooth but heavier to export.</source>
        <translation>Bilder pro Sekunde. 24 wirkt filmisch, 30 ist Standard, 60 ist sehr flüssig, aber exportintensiver.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="617"/>
        <source>How strongly the image slowly enlarges over the full video length.</source>
        <translation>Wie stark sich das Bild über die gesamte Videolänge langsam vergrößert.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="622"/>
        <source>Slow rotation of the image over the full video length. Positive values rotate clockwise.</source>
        <translation>Langsame Drehung des Bilds über die gesamte Videolänge. Positive Werte drehen im Uhrzeigersinn.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="639"/>
        <source>How many stars are generated. Presets set the count automatically; Custom lets you choose the exact number.</source>
        <translation>Anzahl der generierten Sterne. Voreinstellungen setzen die Anzahl automatisch; bei Benutzerdefiniert wählst du die genaue Zahl.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="654"/>
        <source>Pixel size of the faintest stars. Keep this below largest stars for a natural look.</source>
        <translation>Pixelgröße der schwächsten Sterne. Sollte unter der größten Sterngröße liegen für ein natürliches Ergebnis.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="676"/>
        <source>Overall brightness multiplier for all stars. 100% is the default look.</source>
        <translation>Gesamte Helligkeitsverstärkung aller Sterne. 100 % ist der Standardlook.</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="702"/>
        <source>Flight speed</source>
        <translation>Fluggeschwindigkeit</translation>
    </message>
    <message>
        <location filename="../views/widgets/settings_panel.py" line="544"/>
        <location filename="../views/widgets/settings_panel.py" line="834"/>
        <source>No image loaded</source>
        <translation>Kein Bild geladen</translation>
    </message>
</context>
<context>
    <name>TimelineWidget</name>
    <message>
        <location filename="../views/widgets/timeline_widget.py" line="175"/>
        <source>Previous frame</source>
        <translation>Vorheriger Frame</translation>
    </message>
    <message>
        <location filename="../views/widgets/timeline_widget.py" line="176"/>
        <source>Play / Pause</source>
        <translation>Wiedergabe / Pause</translation>
    </message>
    <message>
        <location filename="../views/widgets/timeline_widget.py" line="177"/>
        <source>Stop</source>
        <translation>Stopp</translation>
    </message>
    <message>
        <location filename="../views/widgets/timeline_widget.py" line="178"/>
        <source>Next frame</source>
        <translation>Nächster Frame</translation>
    </message>
</context>
<context>
    <name>Validation</name>
    <message>
        <location filename="__init__.py" line="23"/>
        <source>Please load an image first.</source>
        <translation>Bitte lade zuerst ein Bild.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="26"/>
        <source>The image was not found. Please load it again.</source>
        <translation>Das Bild wurde nicht gefunden. Bitte lade es erneut.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="29"/>
        <source>Target resolution must be at least 480 pixels.</source>
        <translation>Die Zielauflösung muss mindestens 480 Pixel betragen.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="32"/>
        <source>Width and height must be even numbers.</source>
        <translation>Breite und Höhe müssen gerade Zahlen sein.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="35"/>
        <source>Video length must be between 3 and 60 seconds.</source>
        <translation>Die Videolänge muss zwischen 3 und 60 Sekunden liegen.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="38"/>
        <source>Frame rate must be 24, 30, or 60 fps.</source>
        <translation>Die Bildrate muss 24, 30 oder 60 fps betragen.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="41"/>
        <source>Star count must be between 50 and 3000.</source>
        <translation>Die Sternanzahl muss zwischen 50 und 3000 liegen.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="44"/>
        <source>The smallest star size must be below the largest.</source>
        <translation>Die kleinste Sterngröße muss unter der größten liegen.</translation>
    </message>
    <message>
        <location filename="__init__.py" line="48"/>
        <source>FFmpeg was not found. Install FFmpeg and make sure it is available on PATH.</source>
        <translation>FFmpeg wurde nicht gefunden. Installiere FFmpeg und stell sicher, dass es über PATH verfügbar ist.</translation>
    </message>
</context>
<context>
    <name>VideoSaveDialog</name>
    <message>
        <location filename="../views/dialogs/video_save_dialog.py" line="17"/>
        <source>Save video</source>
        <translation>Video speichern</translation>
    </message>
    <message>
        <location filename="../views/dialogs/video_save_dialog.py" line="21"/>
        <source>MP4 Video (*.mp4)</source>
        <translation>MP4-Video (*.mp4)</translation>
    </message>
    <message>
        <location filename="../views/dialogs/video_save_dialog.py" line="24"/>
        <source>Save</source>
        <translation>Speichern</translation>
    </message>
    <message>
        <location filename="../views/dialogs/video_save_dialog.py" line="25"/>
        <source>Cancel</source>
        <translation>Abbrechen</translation>
    </message>
</context>
<context>
    <name>WelcomeSplash</name>
    <message>
        <location filename="../views/widgets/welcome_splash.py" line="130"/>
        <source>Close</source>
        <translation>Schließen</translation>
    </message>
    <message>
        <location filename="../views/widgets/welcome_splash.py" line="132"/>
        <source>Version {version} · Build {build}</source>
        <translation>Version {version} · Build {build}</translation>
    </message>
</context>
<context>
    <name>ZoomToolbar</name>
    <message>
        <location filename="../views/widgets/zoom_toolbar.py" line="27"/>
        <location filename="../views/widgets/zoom_toolbar.py" line="50"/>
        <source>Fit to view</source>
        <translation>An Ansicht anpassen</translation>
    </message>
    <message>
        <location filename="../views/widgets/zoom_toolbar.py" line="28"/>
        <location filename="../views/widgets/zoom_toolbar.py" line="51"/>
        <source>Zoom out</source>
        <translation>Verkleinern</translation>
    </message>
    <message>
        <location filename="../views/widgets/zoom_toolbar.py" line="29"/>
        <location filename="../views/widgets/zoom_toolbar.py" line="52"/>
        <source>Zoom in</source>
        <translation>Vergrößern</translation>
    </message>
    <message>
        <location filename="../views/widgets/zoom_toolbar.py" line="69"/>
        <source>With stars</source>
        <translation>Mit Sternen</translation>
    </message>
    <message>
        <location filename="../views/widgets/zoom_toolbar.py" line="71"/>
        <source>Without stars</source>
        <translation>Ohne Sterne</translation>
    </message>
</context>
<context>
    <name>_FocusPointsCanvas</name>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="280"/>
        <source>Load an image to set the camera path.</source>
        <translation>Lade ein Bild, um den Kamerapfad festzulegen.</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="301"/>
        <source>S</source>
        <translation>S</translation>
    </message>
    <message>
        <location filename="../views/widgets/focus_points_control.py" line="303"/>
        <source>T</source>
        <translation>Z</translation>
    </message>
</context>
</TS>
