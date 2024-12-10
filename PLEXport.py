import os
import sqlite3
import pandas as pd
import datetime
import logging
from typing import List

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText

try:
    from plexapi.server import PlexServer

    PLEXAPI_AVAILABLE = True
except ImportError:
    PLEXAPI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Verzeichnisse & Logging-Konfiguration
# ---------------------------------------------------------------------------
BASE_DIR = r"C:\PLEXport"
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

log_file = os.path.join(BASE_DIR, "plex_gui.log")

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(filename=log_file, level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("plex_gui")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def convert_ms_to_hhmm(ms: int) -> str:
    if pd.isnull(ms):
        return ""
    ms = int(ms)
    seconds = ms // 1000
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def unix_to_datetime_str(timestamp: int) -> str:
    try:
        dt = datetime.datetime.utcfromtimestamp(timestamp)
        return dt.strftime("%d.%m.%Y %H:%M:%S")
    except:
        return ""


# ---------------------------------------------------------------------------
# Funktionen für Plex Server-Verbindung (Live)
# ---------------------------------------------------------------------------
def get_plex_server(baseurl: str, token: str):
    logger.info("Versuche, Verbindung zum Plex-Server aufzubauen.")
    if not PLEXAPI_AVAILABLE:
        messagebox.showerror(
            "Fehler",
            "plexapi ist nicht installiert. Bitte installieren Sie plexapi zuerst.",
        )
        logger.error("Fehler: plexapi nicht verfügbar.")
        return None
    try:
        plex = PlexServer(baseurl, token)
        logger.info("Verbindung zum Plex-Server hergestellt.")
        return plex
    except Exception as e:
        messagebox.showerror(
            "Fehler", f"Verbindung zum Plex-Server fehlgeschlagen:\n{e}"
        )
        logger.error(f"Fehler bei Verbindung zum Plex-Server: {e}")
        return None


# ---------------------------------------------------------------------------
# Funktionen für lokale SQLite-Datenbank
# ---------------------------------------------------------------------------
def connect_to_db(db_path: str) -> sqlite3.Connection:
    logger.info(f"Stelle Verbindung zur lokalen DB her: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        logger.info("Verbindung zur lokalen SQLite-Datenbank erfolgreich.")
        return conn
    except Exception as e:
        messagebox.showerror("Fehler", f"Verbindung zur SQLite-DB fehlgeschlagen:\n{e}")
        logger.error(f"Fehler beim Verbinden zur SQLite-DB: {e}")
        return None


def list_tables(conn: sqlite3.Connection) -> List[str]:
    logger.debug("Liste alle Tabellen der SQLite-DB auf.")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    return [row[0] for row in cursor.fetchall()]


def load_table_as_dataframe(conn: sqlite3.Connection, table_name: str) -> pd.DataFrame:
    logger.debug(f"Lade ersten 10 Datensätze aus Tabelle {table_name}")
    query = f"SELECT * FROM {table_name} LIMIT 10"
    return pd.read_sql_query(query, conn)


def list_libraries(conn: sqlite3.Connection) -> pd.DataFrame:
    logger.debug("Lade Mediatheken aus Tabelle library_sections.")
    query = "SELECT id, name FROM library_sections"
    return pd.read_sql_query(query, conn)


def get_library_details(
    conn: sqlite3.Connection, library_id: int, metadata_type: int
) -> pd.DataFrame:
    logger.debug(
        f"Lade Details für Mediathek-ID {library_id} mit metadata_type {metadata_type}"
    )
    query = f"""
    SELECT
        mi.id,
        mi.title,
        mi.studio,
        mi.summary,
        CAST(mi.duration as INTEGER) as duration,
        GROUP_CONCAT(CASE WHEN t.tag_type=1 THEN t.tag END, '|') AS tags_genre,
        GROUP_CONCAT(CASE WHEN t.tag_type=4 THEN t.tag END, '|') AS tags_director,
        mi.year,
        mi.added_at,
        GROUP_CONCAT(CASE WHEN t.tag_type=5 THEN t.tag END, '|') AS tags_country,
        mi.audience_rating
    FROM metadata_items mi
    LEFT JOIN taggings tg ON mi.id = tg.metadata_item_id
    LEFT JOIN tags t ON tg.tag_id = t.id
    WHERE mi.library_section_id = {library_id}
      AND mi.metadata_type = {metadata_type}
    GROUP BY mi.id
    """

    df = pd.read_sql_query(query, conn)

    # Dauer in HH:MM umwandeln
    if "duration" in df.columns:
        df["duration"] = df["duration"].apply(
            lambda ms: convert_ms_to_hhmm(ms) if pd.notnull(ms) else ""
        )

    # added_at konvertieren
    if "added_at" in df.columns:
        df["added_at"] = df["added_at"].apply(
            lambda x: unix_to_datetime_str(x) if pd.notnull(x) else ""
        )

    # audience_rating formatieren: Komma anstatt Punkt
    if "audience_rating" in df.columns:
        df["audience_rating"] = df["audience_rating"].apply(
            lambda r: f"{r:.1f}".replace(".", ",") if pd.notnull(r) else ""
        )

    return df


def count_items_in_library(
    conn: sqlite3.Connection, library_id: int, metadata_type: int
) -> int:
    logger.debug(
        f"Zähle Inhalte für Mediathek-ID {library_id} mit metadata_type {metadata_type}"
    )
    query = f"""
    SELECT COUNT(*) as cnt
    FROM metadata_items
    WHERE library_section_id = {library_id} AND metadata_type = {metadata_type}
    """
    df = pd.read_sql_query(query, conn)
    return df["cnt"].iloc[0] if not df.empty else 0


# ---------------------------------------------------------------------------
# Funktionen für Live-Bibliothek
# ---------------------------------------------------------------------------
def get_library_details_live(plex, library_id: int, metadata_type: int) -> pd.DataFrame:
    logger.debug(
        f"Lade Live-Details für Mediathek-ID {library_id}, Typ {metadata_type}"
    )
    section = None
    for s in plex.library.sections():
        if s.key == library_id:
            section = s
            break

    if section is None:
        logger.warning("Keine entsprechende Live-Mediathek gefunden.")
        return pd.DataFrame()

    lib_type = "movie" if metadata_type == 1 else "show"
    items = section.all(libtype=lib_type)
    data = []
    for item in items:
        duration_str = convert_ms_to_hhmm(item.duration) if item.duration else ""
        audience_rating_str = ""
        if hasattr(item, "audienceRating") and item.audienceRating:
            audience_rating_str = f"{item.audienceRating:.1f}".replace(".", ",")

        row = {
            "id": item.ratingKey,
            "title": item.title,
            "studio": item.studio if hasattr(item, "studio") else "",
            "summary": item.summary if hasattr(item, "summary") else "",
            "duration": duration_str,
            "tags_genre": "|".join([g.tag for g in item.genres]) if item.genres else "",
            "tags_director": (
                "|".join([d.tag for d in item.directors])
                if hasattr(item, "directors") and item.directors
                else ""
            ),
            "year": item.year,
            "added_at": (
                item.addedAt.strftime("%d.%m.%Y %H:%M:%S") if item.addedAt else ""
            ),
            "tags_country": (
                "|".join([c.tag for c in item.countries])
                if hasattr(item, "countries") and item.countries
                else ""
            ),
            "audience_rating": audience_rating_str,
        }
        data.append(row)
    df = pd.DataFrame(data)
    return df


def get_library_details_live_numeric(
    plex, library_id: int, metadata_type: int
) -> pd.DataFrame:
    # Liefert nur duration numerisch für Statistik
    logger.debug(
        f"Lade Live-Details (numeric) für Stats: ID {library_id}, Typ {metadata_type}"
    )
    section = None
    for s in plex.library.sections():
        if s.key == library_id:
            section = s
            break
    if section is None:
        return pd.DataFrame()

    lib_type = "movie" if metadata_type == 1 else "show"
    items = section.all(libtype=lib_type)
    data = []
    for item in items:
        data.append({"duration": item.duration if item.duration else None})
    df = pd.DataFrame(data)
    return df


# ---------------------------------------------------------------------------
# Funktion zum Vergleichen von zwei Excel-Exports
# ---------------------------------------------------------------------------
def compare_excel_files(file1: str, file2: str, output_file: str):
    logger.info(
        f"Vergleiche Excel-Dateien:\nDatei1: {file1}\nDatei2: {file2}\nAusgabe: {output_file}"
    )

    df1 = pd.read_excel(file1)
    df2 = pd.read_excel(file2)

    set1 = set(df1["title"].astype(str))
    set2 = set(df2["title"].astype(str))

    in1_not_in2_titles = set1 - set2
    in2_not_in1_titles = set2 - set1
    in_both_titles = set1.intersection(set2)

    in1_not_in2 = df1[df1["title"].astype(str).isin(in1_not_in2_titles)]
    in2_not_in1 = df2[df2["title"].astype(str).isin(in2_not_in1_titles)]
    in_both = df1[df1["title"].astype(str).isin(in_both_titles)]

    with pd.ExcelWriter(output_file) as writer:
        in1_not_in2.to_excel(writer, sheet_name="In1NichtIn2", index=False)
        in2_not_in1.to_excel(writer, sheet_name="In2NichtIn1", index=False)
        in_both.to_excel(writer, sheet_name="InBeiden", index=False)

    logger.info("Vergleich abgeschlossen.")


# ---------------------------------------------------------------------------
# Haupt-GUI-Klasse
# ---------------------------------------------------------------------------
class PlexGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Plex Mediathek Auswertung")
        self.geometry("900x700")

        # Voreinstellungen
        self.connection_type = tk.StringVar(value="local")  # "local" oder "live"
        self.db_path = tk.StringVar(
            value="C:/Users/asi/Downloads/Plex Media Server Databases_2024-11-11_00-28-24/databaseBackup.db"
        )
        self.baseurl = tk.StringVar(value="http://192.168.1.2:32400")
        self.token = tk.StringVar(value="rZGHLfs2PqSbZQAAXSfg")

        self.conn = None
        self.plex = None
        self.libraries_df = pd.DataFrame()
        self.selected_library = None
        self.metadata_type = tk.IntVar(value=1)  # Standard: Filme

        self.progress_var = tk.IntVar(value=0)

        self.create_widgets()

    def create_widgets(self):
        # Frame für Verbindungsauswahl
        connection_frame = tk.Frame(self)
        connection_frame.pack(pady=10, padx=10, fill=tk.X)

        tk.Radiobutton(
            connection_frame,
            text="Lokale DB",
            variable=self.connection_type,
            value="local",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(connection_frame, text="DB-Pfad:").grid(row=0, column=1, sticky="e")
        tk.Entry(connection_frame, textvariable=self.db_path, width=40).grid(
            row=0, column=2, padx=5
        )
        tk.Button(connection_frame, text="Browse", command=self.browse_db).grid(
            row=0, column=3, padx=5
        )

        tk.Radiobutton(
            connection_frame,
            text="Live-Plex",
            variable=self.connection_type,
            value="live",
        ).grid(row=1, column=0, sticky="w")
        tk.Label(connection_frame, text="Base-URL:").grid(row=1, column=1, sticky="e")
        tk.Entry(connection_frame, textvariable=self.baseurl, width=40).grid(
            row=1, column=2, padx=5
        )
        tk.Label(connection_frame, text="Token:").grid(row=2, column=1, sticky="e")
        tk.Entry(connection_frame, textvariable=self.token, width=40).grid(
            row=2, column=2, padx=5
        )

        tk.Button(connection_frame, text="Verbinden", command=self.connect_source).grid(
            row=3, column=2, pady=10
        )

        # Frame für Mediatheken
        library_frame = tk.Frame(self)
        library_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Listbox für Mediatheken
        self.library_list = tk.Listbox(library_frame, height=10)
        self.library_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar für Mediatheken
        scrollbar = tk.Scrollbar(
            library_frame, orient=tk.VERTICAL, command=self.library_list.yview
        )
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.library_list.config(yscrollcommand=scrollbar.set)

        # Frame rechts neben der Liste für Buttons
        btn_frame = tk.Frame(library_frame)
        btn_frame.pack(side=tk.LEFT, padx=10, fill=tk.Y)

        tk.Label(btn_frame, text="Mediatyp auswählen:").pack(pady=(0, 5))
        tk.Radiobutton(
            btn_frame, text="Filme (1)", variable=self.metadata_type, value=1
        ).pack(anchor="w")
        tk.Radiobutton(
            btn_frame, text="Serien (4)", variable=self.metadata_type, value=4
        ).pack(anchor="w")

        tk.Button(
            btn_frame,
            text="Mediathek-Statistik anzeigen",
            command=self.show_library_stats,
        ).pack(pady=5)
        tk.Button(
            btn_frame, text="Mediathek exportieren", command=self.export_library
        ).pack(pady=5)
        tk.Button(
            btn_frame,
            text="Excel-Vergleich durchführen",
            command=self.open_compare_dialog,
        ).pack(pady=5)
        tk.Button(btn_frame, text="Hilfe / About", command=self.show_help).pack(pady=5)
        tk.Button(btn_frame, text="Beenden", command=self.quit).pack(pady=5)

        # Frame für Text-Output
        text_output_frame = tk.Frame(self)
        text_output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.text_output = ScrolledText(text_output_frame, wrap=tk.WORD, height=10)
        self.text_output.pack(fill=tk.BOTH, expand=True)

        # Frame für Ladebalken
        progress_frame = tk.Frame(self)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            length=100,
            mode="determinate",
            variable=self.progress_var,
        )
        self.progress_bar.pack(fill=tk.X, expand=True)

    def browse_db(self):
        db_file = filedialog.askopenfilename(
            title="SQLite DB auswählen", filetypes=[("All Files", "*.*")]
        )
        if db_file:
            self.db_path.set(db_file)

    def connect_source(self):
        self.set_progress(0)
        self.text_output.delete("1.0", tk.END)
        self.library_list.delete(0, tk.END)

        ctype = self.connection_type.get()
        logger.info(f"Ausgewählte Datenquelle: {ctype}")

        if ctype == "local":
            dbp = self.db_path.get()
            if not dbp:
                messagebox.showwarning("Warnung", "Bitte DB-Pfad angeben.")
                logger.warning("Kein DB-Pfad angegeben.")
                return
            self.conn = connect_to_db(dbp)
            self.plex = None
            if self.conn:
                self.load_libraries_local()
        else:
            if not PLEXAPI_AVAILABLE:
                messagebox.showerror(
                    "Fehler", "Für die Live-Verbindung ist plexapi erforderlich."
                )
                return
            base = self.baseurl.get()
            tok = self.token.get()
            if not base or not tok:
                messagebox.showwarning("Warnung", "Bitte Base-URL und Token angeben.")
                logger.warning("Base-URL oder Token fehlen für Live-Verbindung.")
                return
            self.plex = get_plex_server(base, tok)
            self.conn = None
            if self.plex:
                self.load_libraries_live()
        self.set_progress(100)

    def load_libraries_local(self):
        try:
            df = list_libraries(self.conn)
            self.libraries_df = df
            self.text_output.insert(tk.END, "Mediatheken (Lokal) geladen.\n")
            for i, row in df.iterrows():
                self.library_list.insert(tk.END, f"{row['id']} - {row['name']}")
            logger.info("Lokale Mediatheken wurden geladen.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Mediatheken nicht laden: {e}")
            logger.error(f"Fehler beim Laden lokaler Mediatheken: {e}")

    def load_libraries_live(self):
        try:
            sections = self.plex.library.sections()
            data = [(s.key, s.title) for s in sections]
            self.libraries_df = pd.DataFrame(data, columns=["id", "name"])
            self.text_output.insert(tk.END, "Mediatheken (Live) geladen.\n")
            for idx, row in self.libraries_df.iterrows():
                self.library_list.insert(tk.END, f"{row['id']} - {row['name']}")
            logger.info("Live-Mediatheken wurden geladen.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Konnte Live-Mediatheken nicht laden: {e}")
            logger.error(f"Fehler beim Laden von Live-Mediatheken: {e}")

    def show_library_stats(self):
        self.set_progress(0)
        self.text_output.delete("1.0", tk.END)
        selection = self.library_list.curselection()
        if not selection:
            messagebox.showinfo("Info", "Bitte eine Mediathek auswählen.")
            logger.info("Keine Mediathek ausgewählt.")
            return
        idx = selection[0]
        lib_id, lib_name = self.parse_library_item(self.library_list.get(idx))
        self.selected_library = (lib_id, lib_name)
        mtype = self.metadata_type.get()
        logger.info(
            f"Zeige Statistik für Mediathek-ID: {lib_id}, Name: {lib_name}, Typ: {mtype}"
        )

        if self.conn:  # Lokale DB
            df = get_library_details(self.conn, lib_id, mtype)
            # Für Statistik noch einmal numeric duration
            query_for_stats = f"""
            SELECT CAST(duration as INTEGER) as duration
            FROM metadata_items
            WHERE library_section_id = {lib_id}
              AND metadata_type = {mtype}
            """
            df_stats = pd.read_sql_query(query_for_stats, self.conn)
        else:
            df = get_library_details_live(self.plex, lib_id, mtype)
            df_stats = get_library_details_live_numeric(self.plex, lib_id, mtype)

        if df is None or df.empty or df_stats.empty:
            self.text_output.insert(tk.END, f"Keine Daten für {lib_name}.\n")
            logger.info("Keine Daten für diese Mediathek gefunden.")
            return

        df_stats["duration"] = pd.to_numeric(df_stats["duration"], errors="coerce")
        count = len(df_stats)
        total_duration = df_stats["duration"].sum()
        avg_duration = total_duration / count if count > 0 else 0
        avg_duration_str = convert_ms_to_hhmm(avg_duration) if avg_duration > 0 else ""

        avg_rating = None
        if "audience_rating" in df.columns and df["audience_rating"].notnull().any():
            # audience_rating zurück zu float
            df["audience_rating_num"] = (
                df["audience_rating"]
                .str.replace(",", ".")
                .astype(float, errors="ignore")
            )
            if df["audience_rating_num"].dtype == float:
                avg_rating = df["audience_rating_num"].mean()

        total_h, total_m = divmod((total_duration // 1000) // 60, 60)
        stats_text = f"Mediathek: {lib_name}\n"
        stats_text += f"Anzahl Inhalte: {count}\n"
        stats_text += f"Gesamtdauer: {int(total_h)}h {int(total_m)}m\n"
        stats_text += f"Durchschnittliche Dauer: {avg_duration_str}\n"
        if avg_rating is not None:
            stats_text += f"Durchschnittliches Rating: {avg_rating:.2f}\n"

        self.text_output.insert(tk.END, stats_text)
        self.set_progress(100)

    def export_library(self):
        self.set_progress(0)
        selection = self.library_list.curselection()
        if not selection:
            messagebox.showinfo("Info", "Bitte eine Mediathek auswählen.")
            logger.info("Keine Mediathek zum Export ausgewählt.")
            return
        idx = selection[0]
        lib_id, lib_name = self.parse_library_item(self.library_list.get(idx))
        mtype = self.metadata_type.get()
        logger.info(
            f"Exportiere Mediathek-ID: {lib_id}, Name: {lib_name}, Typ: {mtype}"
        )

        if self.conn:  # Lokale DB
            df = get_library_details(self.conn, lib_id, mtype)
        else:
            df = get_library_details_live(self.plex, lib_id, mtype)

        if df is None or df.empty:
            messagebox.showinfo("Info", f"Keine Daten für {lib_name} zum Export.")
            logger.info("Keine Daten zum Export.")
            return

        # Benutzer wählt Speicherort
        save_path = filedialog.asksaveasfilename(
            title="Speicherort für Excel wählen",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
        )

        if not save_path:
            logger.info("Benutzer hat den Speichern-Dialog abgebrochen.")
            return

        # Normaler Export
        try:
            df.to_excel(save_path, index=False)
            messagebox.showinfo("Erfolg", f"Export abgeschlossen: {save_path}")
            logger.info(f"Export erfolgreich: {save_path}")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Export: {e}")
            logger.error(f"Fehler beim Export: {e}")
            return

        # Zusätzlich in C:\PLEXport\ mit Datum/Zeit Prefix speichern
        now_str = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        filename = f"{now_str}_{os.path.basename(save_path)}"
        backup_path = os.path.join(BASE_DIR, filename)
        try:
            df.to_excel(backup_path, index=False)
            logger.info(f"Zusätzlicher Export in {backup_path}")
        except Exception as e:
            logger.error(f"Fehler beim Backup-Export: {e}")

        self.set_progress(100)

    def parse_library_item(self, item: str):
        # Format: "id - name"
        parts = item.split(" - ", 1)
        lib_id = int(parts[0])
        lib_name = parts[1]
        return lib_id, lib_name

    def open_compare_dialog(self):
        self.set_progress(0)
        file1 = filedialog.askopenfilename(
            title="Excel-Datei 1 wählen",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
        )
        if not file1:
            return
        file2 = filedialog.askopenfilename(
            title="Excel-Datei 2 wählen",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
        )
        if not file2:
            return
        output_file = filedialog.asksaveasfilename(
            title="Zieldatei wählen",
            defaultextension=".xlsx",
            filetypes=[("Excel Files", "*.xlsx"), ("All Files", "*.*")],
        )
        if not output_file:
            return

        compare_excel_files(file1, file2, output_file)
        messagebox.showinfo(
            "Fertig", f"Vergleich abgeschlossen.\nErgebnis: {output_file}"
        )
        # Zusätzlich in C:\PLEXport\ mit Datum/Zeit Prefix speichern
        now_str = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        backup_filename = f"{now_str}_{os.path.basename(output_file)}"
        backup_path = os.path.join(BASE_DIR, backup_filename)
        try:
            # Kopie der Vergleichsdatei erstellen
            df_in1_not_in2 = pd.read_excel(output_file, sheet_name="In1NichtIn2")
            df_in2_not_in1 = pd.read_excel(output_file, sheet_name="In2NichtIn1")
            df_inboth = pd.read_excel(output_file, sheet_name="InBeiden")

            with pd.ExcelWriter(backup_path) as writer:
                df_in1_not_in2.to_excel(writer, sheet_name="In1NichtIn2", index=False)
                df_in2_not_in1.to_excel(writer, sheet_name="In2NichtIn1", index=False)
                df_inboth.to_excel(writer, sheet_name="InBeiden", index=False)
            logger.info(f"Backup des Vergleichs unter {backup_path}")
        except Exception as e:
            logger.error(f"Fehler beim Backup des Vergleichs: {e}")

        self.set_progress(100)

    def show_help(self):
        help_text = """## Plex Datenbank herunterladen
1. Rufe die Plex Einstellungen auf (https://app.plex.tv/desktop/#!/settings/web/general)
2. Scrolle ganz runter zu "Fehlerbehebung"
3. Klicke auf Datenbank exportieren
4. Gib im Programm den Pfad zur DB an (ohne Anführungszeichen) und verwende den DB-Export indem du auf Verbinden klickst.

## Plex Live-Zugriff
1. Gib deine Base-URL an, das ist idR http://ip-des-servers:32400

## Plex Token auslesen
1. Rufe Plex auf (https://app.plex.tv/).
2. Gehe zu einem beliebigen Film in deiner Sammlung.
3. Klicke auf die drei Punkte und wähle im Menü "Medieninfo".
4. Klicke auf "XML-Datei anzeigen".
5. Scrolle ans Ende der URL und kopiere den Teil hinter token=, z.B. U3GHLfkhPqSbZQAAXSfg.
6. Gib den Token "pur" im Programm ein und klicke auf Verbinden.

Copyright by sp23 feat. ChatGPT o1
"""
        messagebox.showinfo("Hilfe / About", help_text)

    def set_progress(self, value: int):
        self.progress_var.set(value)
        self.update_idletasks()


if __name__ == "__main__":
    app = PlexGUI()
    app.mainloop()
