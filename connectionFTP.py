import os
from pathlib import Path
import paramiko
import sys
import logging
from datetime import datetime
import json

# ============================================
# CONFIGURACIÓN - RELLENA TUS DATOS AQUÍ
# ============================================
SFTP_CONFIG = {
    'SFTP_HOST': 'ftp.sistemaicom.com',        # Tu servidor FTP
    'SFTP_USER': 'sisicom',                     # Tu usuario
    'SFTP_PASS': 'tu_contraseña_aqui',          # Tu contraseña
    'SFTP_PORT': 223,                           # Puerto (normalmente 22 para SFTP)
    'LOCAL_FOLDER': 'C:/ruta/a/tu/carpeta',     # Carpeta local a subir
    'REMOTE_FOLDER': '/ruta/en/el/servidor'     # Carpeta destino en servidor
}
# ============================================

def setup_logging():
    """Configurar el sistema de logging"""
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    log_filename = f"logs/sftp_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filename, encoding='utf-8'),
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

def validate_config():
    """Validar que todas las variables de configuración estén presentes"""
    required_vars = ['SFTP_HOST', 'SFTP_USER', 'SFTP_PASS', 'LOCAL_FOLDER', 'REMOTE_FOLDER']
    
    missing_vars = [var for var in required_vars if not SFTP_CONFIG.get(var)]
    if missing_vars:
        logger.error(f"Faltan las siguientes variables de configuración: {', '.join(missing_vars)}")
        sys.exit(1)
    
    # Verificar que la carpeta local exista
    if not os.path.exists(SFTP_CONFIG['LOCAL_FOLDER']):
        logger.error(f"La carpeta local no existe: {SFTP_CONFIG['LOCAL_FOLDER']}")
        sys.exit(1)
    
    return SFTP_CONFIG

def get_sftp_connection(config):
    """Establecer conexión SFTP con Paramiko"""
    try:
        # Crear cliente SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Conectar
        ssh.connect(
            hostname=config['SFTP_HOST'],
            port=config['SFTP_PORT'],
            username=config['SFTP_USER'],
            password=config['SFTP_PASS'],
            look_for_keys=False,
            allow_agent=False
        )
        
        # Abrir canal SFTP
        sftp = ssh.open_sftp()
        
        logger.info(f"Conectado exitosamente a {config['SFTP_HOST']}:{config['SFTP_PORT']} usando SFTP")
        return ssh, sftp
        
    except Exception as e:
        logger.error(f"Error al conectar al SFTP: {str(e)}")
        sys.exit(1)

def remote_path_exists(sftp, path):
    """Verificar si una ruta remota existe"""
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False

def upload_file(sftp, local_path, remote_path, stats):
    """Subir un archivo al servidor SFTP"""
    try:
        sftp.put(local_path, remote_path)
        
        # Preservar tiempo de modificación
        local_stat = os.stat(local_path)
        sftp.utime(remote_path, (local_stat.st_atime, local_stat.st_mtime))
        
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
        if not remote_path_exists(sftp, remote_dir):
            # Crear directorios padre si no existen
            parent_dir = str(Path(remote_dir).parent).replace('\\', '/')
            if parent_dir != '/' and not remote_path_exists(sftp, parent_dir):
                create_remote_directory(sftp, parent_dir, stats)
            
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
    
    # Crear directorio remoto base si no existe
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
    
    ssh = None
    sftp = None
    
    try:
        # Validar configuración
        logger.info("Iniciando proceso de sincronización SFTP")
        config = validate_config()
        
        # Conectar al SFTP
        ssh, sftp = get_sftp_connection(config)
        
        # Subir archivos
        upload_directory(sftp, config['LOCAL_FOLDER'], config['REMOTE_FOLDER'], stats)
        
        # Guardar reporte
        report_file = stats.save_report()
        logger.info(f"Reporte de sincronización guardado en: {report_file}")
        
        # Mostrar resumen
        logger.info(f"""
╔════════════════════════════════════════════╗
║     RESUMEN DE SINCRONIZACIÓN SFTP        ║
╚════════════════════════════════════════════╝
✓ Archivos subidos exitosamente: {len(stats.files_uploaded)}
✗ Archivos con errores: {len(stats.files_failed)}
📁 Directorios creados: {len(stats.directories_created)}
⏱ Tiempo total: {(datetime.now() - stats.start_time).total_seconds():.2f} segundos
""")
        
    except Exception as e:
        logger.error(f"Error durante la sincronización: {str(e)}")
        stats.end_time = datetime.now()
        stats.save_report()
        sys.exit(1)
    
    finally:
        # Cerrar conexiones
        if sftp:
            sftp.close()
            logger.info("Conexión SFTP cerrada")
        if ssh:
            ssh.close()
            logger.info("Conexión SSH cerrada")

if __name__ == "__main__":
    main()