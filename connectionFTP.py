import os
from ftplib import FTP
from dotenv import load_dotenv
import sys
import logging
from pathlib import Path
from datetime import datetime
import json

def setup_logging():
    """Configurar el sistema de logging"""
    # Crear directorio de logs si no existe
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Nombre del archivo de log con fecha
    log_filename = f"logs/ftp_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Configurar logging para archivo y consola
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class FTPSyncStats:
    """Clase para mantener estadísticas de la sincronización"""
    def __init__(self):
        self.files_uploaded = []
        self.files_failed = []
        self.directories_created = []
        self.start_time = datetime.now()
        self.end_time = None
    
    def to_dict(self):
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() if self.end_time else None,
            'files_uploaded': self.files_uploaded,
            'files_failed': self.files_failed,
            'directories_created': self.directories_created,
            'total_files_uploaded': len(self.files_uploaded),
            'total_files_failed': len(self.files_failed),
            'total_directories_created': len(self.directories_created)
        }
    
    def save_report(self):
        """Guardar reporte en formato JSON"""
        self.end_time = datetime.now()
        report_filename = f"logs/sync_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return report_filename

def load_environment():
    """Cargar variables de entorno desde el archivo .env"""
    load_dotenv()
    
    required_vars = ['FTP_HOST', 'FTP_USER', 'FTP_PASS', 'LOCAL_FOLDER', 'REMOTE_FOLDER']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Faltan las siguientes variables de entorno: {', '.join(missing_vars)}")
        sys.exit(1)
    
    return {var: os.getenv(var) for var in required_vars}

def connect_ftp(config):
    """Establecer conexión FTP"""
    try:
        ftp = FTP(config['FTP_HOST'])
        ftp.login(config['FTP_USER'], config['FTP_PASS'])
        logger.info(f"Conectado exitosamente a {config['FTP_HOST']}")
        return ftp
    except Exception as e:
        logger.error(f"Error al conectar al FTP: {str(e)}")
        sys.exit(1)

def upload_file(ftp, local_path, remote_path, stats):
    """Subir un archivo al servidor FTP"""
    try:
        with open(local_path, 'rb') as file:
            ftp.storbinary(f'STOR {remote_path}', file)
        logger.info(f"Archivo subido exitosamente: {remote_path}")
        stats.files_uploaded.append({
            'local_path': str(local_path),
            'remote_path': remote_path,
            'size_bytes': os.path.getsize(local_path),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        error_msg = f"Error al subir {local_path}: {str(e)}"
        logger.error(error_msg)
        stats.files_failed.append({
            'local_path': str(local_path),
            'remote_path': remote_path,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

def create_remote_directory(ftp, remote_dir, stats):
    """Crear directorio remoto y registrar la acción"""
    try:
        ftp.mkd(remote_dir)
        logger.info(f"Directorio creado: {remote_dir}")
        stats.directories_created.append({
            'path': remote_dir,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.debug(f"Directorio ya existe o error al crear {remote_dir}: {str(e)}")

def upload_directory(ftp, local_dir, remote_dir, stats):
    """Subir todos los archivos de un directorio al FTP"""
    local_path = Path(local_dir)
    
    # Crear directorio remoto si no existe
    create_remote_directory(ftp, remote_dir, stats)
    
    # Recorrer todos los archivos y subdirectorios
    for item in local_path.rglob('*'):
        # Calcular la ruta relativa
        relative_path = item.relative_to(local_path)
        remote_path = str(Path(remote_dir) / relative_path).replace('\\', '/')
        
        if item.is_file():
            # Crear directorios remotos necesarios
            remote_item_dir = str(Path(remote_path).parent).replace('\\', '/')
            create_remote_directory(ftp, remote_item_dir, stats)
            
            upload_file(ftp, str(item), remote_path, stats)

def main():
    """Función principal"""
    global logger
    logger = setup_logging()
    
    # Inicializar estadísticas
    stats = FTPSyncStats()
    
    try:
        # Cargar configuración
        logger.info("Iniciando proceso de sincronización FTP")
        config = load_environment()
        
        # Conectar al FTP
        ftp = connect_ftp(config)
        
        # Subir archivos
        upload_directory(ftp, config['LOCAL_FOLDER'], config['REMOTE_FOLDER'], stats)
        
        # Cerrar conexión
        ftp.quit()
        logger.info("Conexión FTP cerrada")
        
        # Guardar reporte
        report_file = stats.save_report()
        logger.info(f"Reporte de sincronización guardado en: {report_file}")
        
        # Mostrar resumen
        logger.info(f"""
Resumen de sincronización:
- Archivos subidos exitosamente: {len(stats.files_uploaded)}
- Archivos con errores: {len(stats.files_failed)}
- Directorios creados: {len(stats.directories_created)}
- Tiempo total: {(datetime.now() - stats.start_time).total_seconds():.2f} segundos
""")
        
    except Exception as e:
        logger.error(f"Error durante la sincronización: {str(e)}")
        stats.end_time = datetime.now()
        stats.save_report()
        sys.exit(1)

if __name__ == "__main__":
    main()