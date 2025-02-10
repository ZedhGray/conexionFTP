import os
from pathlib import Path
import pysftp
from dotenv import load_dotenv
import sys
import logging
from datetime import datetime
import json

def setup_logging():
    """Configurar el sistema de logging"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    log_filename = f"logs/sftp_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

class SFTPSyncStats:
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
    
    required_vars = ['SFTP_HOST', 'SFTP_USER', 'SFTP_PASS', 'LOCAL_FOLDER', 'REMOTE_FOLDER']
    config = {}
    
    # Verificar variables requeridas
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Faltan las siguientes variables de entorno: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Cargar todas las variables
    for var in required_vars:
        config[var] = os.getenv(var)
    
    # Agregar puerto
    config['SFTP_PORT'] = int(os.getenv('SFTP_PORT', '223'))
    
    return config

def get_sftp_connection(config):
    """Establecer conexión SFTP segura"""
    try:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None  # Deshabilitar verificación de hostkeys para coincidir con tu configuración
        
        sftp = pysftp.Connection(
            host=config['SFTP_HOST'],
            username=config['SFTP_USER'],
            password=config['SFTP_PASS'],
            port=config['SFTP_PORT'],
            cnopts=cnopts
        )
        
        logger.info(f"Conectado exitosamente a {config['SFTP_HOST']} usando SFTP")
        return sftp
        
    except Exception as e:
        logger.error(f"Error al conectar al SFTP: {str(e)}")
        sys.exit(1)

def upload_file(sftp, local_path, remote_path, stats):
    """Subir un archivo al servidor SFTP"""
    try:
        sftp.put(local_path, remote_path, preserve_mtime=True)
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

def create_remote_directory(sftp, remote_dir, stats):
    """Crear directorio remoto y registrar la acción"""
    try:
        if not sftp.exists(remote_dir):
            sftp.mkdir(remote_dir)
            logger.info(f"Directorio creado: {remote_dir}")
            stats.directories_created.append({
                'path': remote_dir,
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        logger.debug(f"Error al crear directorio {remote_dir}: {str(e)}")

def upload_directory(sftp, local_dir, remote_dir, stats):
    """Subir todos los archivos de un directorio al SFTP"""
    local_path = Path(local_dir)
    
    # Crear directorio remoto si no existe
    create_remote_directory(sftp, remote_dir, stats)
    
    # Recorrer todos los archivos y subdirectorios
    for item in local_path.rglob('*'):
        # Calcular la ruta relativa
        relative_path = item.relative_to(local_path)
        remote_path = str(Path(remote_dir) / relative_path).replace('\\', '/')
        
        if item.is_file():
            # Crear directorios remotos necesarios
            remote_item_dir = str(Path(remote_path).parent).replace('\\', '/')
            create_remote_directory(sftp, remote_item_dir, stats)
            
            upload_file(sftp, str(item), remote_path, stats)

def main():
    """Función principal"""
    global logger
    logger = setup_logging()
    
    # Inicializar estadísticas
    stats = SFTPSyncStats()
    
    try:
        # Cargar configuración
        logger.info("Iniciando proceso de sincronización SFTP")
        config = load_environment()
        
        # Conectar al SFTP
        with get_sftp_connection(config) as sftp:
            # Subir archivos
            upload_directory(sftp, config['LOCAL_FOLDER'], config['REMOTE_FOLDER'], stats)
            logger.info("Conexión SFTP cerrada")
        
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