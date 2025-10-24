import paramiko
from pathlib import Path

# ============================================
# CONFIGURACIÓN - RELLENA TUS DATOS AQUÍ
# ============================================
SFTP_CONFIG = {
    'SFTP_HOST': 'ftp.sistemaicom.com',
    'SFTP_USER': 'sisicom',
    'SFTP_PASS': 'tu_contraseña_aqui',
    'SFTP_PORT': 223,
    'LOCAL_FOLDER': 'C:/ruta/a/tu/carpeta',
    'REMOTE_FOLDER': '/ruta/en/el/servidor'
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

def create_remote_directory(sftp, remote_dir):
    """Crear directorio remoto"""
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parent_dir = str(Path(remote_dir).parent).replace('\\', '/')
        if parent_dir != '/':
            create_remote_directory(sftp, parent_dir)
        sftp.mkdir(remote_dir)

def upload_directory(sftp, local_dir, remote_dir):
    """Subir todos los archivos al SFTP y borrar local si se subió exitosamente"""
    import os
    local_path = Path(local_dir)
    
    create_remote_directory(sftp, remote_dir)
    
    for item in local_path.rglob('*'):
        if item.is_file():
            relative_path = item.relative_to(local_path)
            remote_path = str(Path(remote_dir) / relative_path).replace('\\', '/')
            remote_item_dir = str(Path(remote_path).parent).replace('\\', '/')
            
            create_remote_directory(sftp, remote_item_dir)
            sftp.put(str(item), remote_path)
            os.remove(str(item))

def main():
    """Función principal"""
    ssh, sftp = get_sftp_connection(SFTP_CONFIG)
    
    try:
        upload_directory(sftp, SFTP_CONFIG['LOCAL_FOLDER'], SFTP_CONFIG['REMOTE_FOLDER'])
    finally:
        sftp.close()
        ssh.close()

if __name__ == "__main__":
    main()