# type: ignore
import paramiko  # type: ignore
from pathlib import Path
import os

# ============================================
# CONFIGURACIÓN - RELLENA TUS DATOS AQUÍ
# ============================================
SFTP_CONFIG = {
    'SFTP_HOST': 'ftp.sistemaicom.com',
    'SFTP_USER': 'sisicom',
    'SFTP_PASS': 'tu_contraseña_aqui',
    'SFTP_PORT': 223,
    'REMOTE_FOLDER': '/ruta/en/el/servidor',
    'LOCAL_FOLDER': 'C:/ruta/destino/local'
}
# ============================================

def get_sftp_connection(config):
    """Establecer conexión SFTP"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    ssh.connect(
        hostname=config['SFTP_HOST'],
        port=config['SFTP_PORT'],
        username=config['SFTP_USER'],
        password=config['SFTP_PASS'],
        look_for_keys=False,
        allow_agent=False
    )
    
    return ssh, ssh.open_sftp()

def download_directory(sftp, remote_dir, local_dir):
    """Descargar todos los archivos del SFTP"""
    
    def download_recursive(remote_path, local_path):
        for item in sftp.listdir_attr(remote_path):
            remote_item = remote_path + '/' + item.filename
            local_item = os.path.join(local_path, item.filename)
            
            if item.st_mode & 0o040000:  # Es directorio
                os.makedirs(local_item, exist_ok=True)
                download_recursive(remote_item, local_item)
            else:  # Es archivo
                sftp.get(remote_item, local_item)
    
    os.makedirs(local_dir, exist_ok=True)
    download_recursive(remote_dir, local_dir)

def main():
    """Función principal"""
    ssh, sftp = get_sftp_connection(SFTP_CONFIG)
    
    try:
        download_directory(sftp, SFTP_CONFIG['REMOTE_FOLDER'], SFTP_CONFIG['LOCAL_FOLDER'])
    finally:
        sftp.close()
        ssh.close()

if __name__ == "__main__":
    main()