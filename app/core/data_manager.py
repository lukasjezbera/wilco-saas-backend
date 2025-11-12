"""
Data Manager Service - Univerzální správa podkladových dat
Podporuje různé moduly (Alza, Financials, Generic)
"""

import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import json


class DataManager:
    """Manager pro načítání, kopírování a správu dat"""
    
    def __init__(self, app_root: Path, db_manager=None):
        """
        Inicializace Data Managera
        
        Args:
            app_root: Kořenová složka aplikace
            db_manager: Database manager pro ukládání metadat
        """
        self.app_root = Path(app_root)
        self.data_folder = self.app_root / "data"
        self.backup_folder = self.data_folder / "backups"
        self.db = db_manager
        
        # Vytvoř složky pokud neexistují
        self.data_folder.mkdir(exist_ok=True)
        self.backup_folder.mkdir(exist_ok=True)
        
        # Načti metadata
        self.metadata = self._load_metadata()
    
    def get_data_folder(self) -> Path:
        """Vrátí cestu k data složce"""
        return self.data_folder
    
    def list_available_files(self) -> List[Dict]:
        """
        Seznam všech dostupných CSV souborů
        
        Returns:
            List of dicts s info o souborech
        """
        files = []
        
        for csv_file in self.data_folder.glob("*.csv"):
            # Skip backup folder
            if "backups" in str(csv_file):
                continue
            
            stat = csv_file.stat()
            
            file_info = {
                'name': csv_file.name,
                'path': str(csv_file),
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'hash': self._calculate_file_hash(csv_file)
            }
            
            # Pokud máme metadata, přidej je
            if csv_file.name in self.metadata.get('files', {}):
                file_info['metadata'] = self.metadata['files'][csv_file.name]
            
            files.append(file_info)
        
        return sorted(files, key=lambda x: x['name'])
    
    def import_files(
        self, 
        source_paths: List[str], 
        create_backup: bool = True
    ) -> Tuple[int, int, List[str]]:
        """
        Importuje (zkopíruje) soubory do data složky
        
        Args:
            source_paths: Seznam cest ke zdrojovým CSV
            create_backup: Zda vytvořit backup před přepsáním
            
        Returns:
            (success_count, error_count, error_messages)
        """
        success = 0
        errors = 0
        error_msgs = []
        
        # Vytvoř backup timestamp
        if create_backup:
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            current_backup = self.backup_folder / backup_time
            current_backup.mkdir(exist_ok=True)
        
        for source_path in source_paths:
            try:
                source = Path(source_path)
                
                # Validace
                if not source.exists():
                    raise FileNotFoundError(f"Soubor nenalezen: {source}")
                
                if not source.suffix.lower() == '.csv':
                    raise ValueError(f"Není CSV soubor: {source.name}")
                
                destination = self.data_folder / source.name
                
                # Backup existujícího souboru
                if destination.exists() and create_backup:
                    backup_dest = current_backup / source.name
                    shutil.copy2(destination, backup_dest)
                
                # Zkopíruj nový soubor
                shutil.copy2(source, destination)
                
                # Ulož metadata
                self._save_file_metadata(
                    filename=source.name,
                    source_path=str(source),
                    imported_at=datetime.now(),
                    file_hash=self._calculate_file_hash(destination)
                )
                
                success += 1
                
            except Exception as e:
                errors += 1
                error_msgs.append(f"{source.name}: {str(e)}")
        
        # Aktualizuj metadata
        self._save_metadata()
        
        return success, errors, error_msgs
    
    def load_dataframe(
        self, 
        filename: str, 
        encoding: str = 'utf-8'
    ) -> Optional[pd.DataFrame]:
        """
        Načte CSV jako DataFrame s automatickou detekcí formátu
        
        Args:
            filename: Název souboru
            encoding: Encoding (default utf-8)
            
        Returns:
            DataFrame nebo None pokud chyba
        """
        file_path = self.data_folder / filename
        
        if not file_path.exists():
            print(f"❌ {filename} - soubor neexistuje!")
            return None
        
        # Zkus různé kombinace separátoru a decimalu
        read_options = [
            # Option 1: UTF-8, středník, čárka (typický český formát)
            {'encoding': 'utf-8', 'sep': ';', 'decimal': ','},
            # Option 2: UTF-8, čárka, tečka (anglický formát)
            {'encoding': 'utf-8', 'sep': ',', 'decimal': '.'},
            # Option 3: Windows-1250, středník, čárka (starší český)
            {'encoding': 'windows-1250', 'sep': ';', 'decimal': ','},
            # Option 4: UTF-8, auto-detect separator
            {'encoding': 'utf-8'},
            # Option 5: ISO-8859-2 (Latin-2)
            {'encoding': 'iso-8859-2', 'sep': ';', 'decimal': ','},
        ]
        
        df = None
        successful_option = None
        errors = []
        
        for i, options in enumerate(read_options, 1):
            try:
                df = pd.read_csv(file_path, **options)
                
                # Validace: DataFrame musí mít alespoň 1 řádek a 1 sloupec
                if df is not None and len(df) > 0 and len(df.columns) > 0:
                    successful_option = i
                    print(f"✅ {filename} načten (option {i}: sep={options.get('sep', 'auto')}, decimal={options.get('decimal', '.')}, encoding={options['encoding']})")
                    break
                else:
                    errors.append(f"Option {i}: Prázdný DataFrame")
                    
            except Exception as e:
                errors.append(f"Option {i}: {str(e)[:100]}")
                continue
        
        if df is None:
            print(f"❌ Nepodařilo se načíst {filename}")
            print(f"   Zkoušené možnosti:")
            for err in errors:
                print(f"   - {err}")
            return None
        
        # Pokus o konverzi sloupců na numeric kde to dává smysl
        for col in df.columns:
            if df[col].dtype == 'object':
                # Zkus převést na numeric (ignoruj chyby)
                df[col] = pd.to_numeric(df[col], errors='ignore')
        
        # Ulož statistiky
        self._save_load_statistics(filename, len(df), len(df.columns))
        
        return df
    
    def load_all_dataframes(
        self, 
        encoding: str = 'utf-8'
    ) -> Dict[str, pd.DataFrame]:
        """
        Načte všechny CSV jako DataFrames
        
        Args:
            encoding: Encoding (default utf-8)
            
        Returns:
            Dict[variable_name, DataFrame]
        """
        dataframes = {}
        
        for file_info in self.list_available_files():
            filename = file_info['name']
            
            # Variable name = filename bez .csv
            var_name = filename.replace('.csv', '')
            
            df = self.load_dataframe(filename, encoding)
            
            if df is not None:
                dataframes[var_name] = df
        
        return dataframes
    
    def get_file_info(self, filename: str) -> Optional[Dict]:
        """
        Získá detailní info o souboru
        
        Args:
            filename: Název souboru
            
        Returns:
            Dict s info nebo None
        """
        file_path = self.data_folder / filename
        
        if not file_path.exists():
            return None
        
        stat = file_path.stat()
        
        info = {
            'name': filename,
            'path': str(file_path),
            'size_bytes': stat.st_size,
            'size_mb': round(stat.st_size / (1024 * 1024), 2),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'created': datetime.fromtimestamp(stat.st_ctime),
            'hash': self._calculate_file_hash(file_path)
        }
        
        # Přidej metadata pokud existují
        if filename in self.metadata.get('files', {}):
            info['metadata'] = self.metadata['files'][filename]
        
        return info
    
    def delete_file(self, filename: str, create_backup: bool = True) -> bool:
        """
        Smaže soubor z data složky
        
        Args:
            filename: Název souboru
            create_backup: Zda vytvořit backup před smazáním
            
        Returns:
            True pokud úspěch
        """
        file_path = self.data_folder / filename
        
        if not file_path.exists():
            return False
        
        try:
            # Backup
            if create_backup:
                backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dest = self.backup_folder / backup_time / filename
                backup_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_dest)
            
            # Smaž
            file_path.unlink()
            
            # Smaž metadata
            if filename in self.metadata.get('files', {}):
                del self.metadata['files'][filename]
                self._save_metadata()
            
            return True
            
        except Exception as e:
            print(f"❌ Chyba při mazání {filename}: {e}")
            return False
    
    def get_data_summary(self) -> Dict:
        """
        Vrátí souhrn všech dat
        
        Returns:
            Dict se statistikami
        """
        files = self.list_available_files()
        
        total_size = sum(f['size_mb'] for f in files)
        
        summary = {
            'total_files': len(files),
            'total_size_mb': round(total_size, 2),
            'files': files,
            'last_import': self.metadata.get('last_import'),
            'data_folder': str(self.data_folder)
        }
        
        return summary
    
    # ==========================================
    # PRIVATE HELPERS
    # ==========================================
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Vypočítá SHA256 hash souboru"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()[:16]
    
    def _load_metadata(self) -> Dict:
        """Načte metadata ze souboru"""
        metadata_file = self.data_folder / "metadata.json"
        
        if not metadata_file.exists():
            return {'files': {}}
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {'files': {}}
    
    def _save_metadata(self):
        """Uloží metadata do souboru"""
        metadata_file = self.data_folder / "metadata.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    def _save_file_metadata(
        self, 
        filename: str, 
        source_path: str,
        imported_at: datetime,
        file_hash: str
    ):
        """Uloží metadata o souboru"""
        if 'files' not in self.metadata:
            self.metadata['files'] = {}
        
        self.metadata['files'][filename] = {
            'source_path': source_path,
            'imported_at': imported_at.isoformat(),
            'file_hash': file_hash
        }
        
        self.metadata['last_import'] = datetime.now().isoformat()
    
    def _save_load_statistics(
        self, 
        filename: str, 
        rows: int, 
        columns: int
    ):
        """Uloží statistiky o načtení"""
        if filename not in self.metadata.get('files', {}):
            return
        
        self.metadata['files'][filename]['last_loaded'] = datetime.now().isoformat()
        self.metadata['files'][filename]['rows'] = rows
        self.metadata['files'][filename]['columns'] = columns
        
        self._save_metadata()
