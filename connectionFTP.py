# type: ignore
import paramiko  # type: ignore
import os
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
    """Subir todos los archivos al SFTP"""
    local_path = Path(local_dir)
    uploaded_files = []
    
    create_remote_directory(sftp, remote_dir)
    
    for item in local_path.rglob('*'):
        if item.is_file():
            relative_path = item.relative_to(local_path)
            remote_path = str(Path(remote_dir) / relative_path).replace('\\', '/')
            remote_item_dir = str(Path(remote_path).parent).replace('\\', '/')
            
            try:
                create_remote_directory(sftp, remote_item_dir)
                sftp.put(str(item), remote_path)
                
                # Verificar que se subió correctamente
                remote_size = sftp.stat(remote_path).st_size
                local_size = item.stat().st_size
                
                if remote_size == local_size:
                    uploaded_files.append(str(item))
                    print(f"✓ Subido: {item.name}")
                else:
                    print(f"✗ Error de tamaño: {item.name}")
                    
            except Exception as e:
                print(f"✗ Error subiendo {item.name}: {e}")
    
    return uploaded_files

def delete_local_files(local_dir):
    """Borrar solo los archivos dentro de la carpeta (mantiene la carpeta vacía)"""
    deleted_count = 0
    error_count = 0
    
    local_path = Path(local_dir)
    
    # Borrar archivos (de más profundo a más superficial)
    for item in sorted(local_path.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        try:
            if item.is_file():
                item.unlink()
                deleted_count += 1
            elif item.is_dir() and item != local_path:
                # Borrar subdirectorios vacíos (pero NO la carpeta principal)
                item.rmdir()
        except Exception as e:
            print(f"✗ Error borrando {item.name}: {e}")
            error_count += 1
    
    print(f"\n✓ Archivos eliminados: {deleted_count}")
    if error_count > 0:
        print(f"✗ Errores: {error_count}")
    
    return deleted_count > 0

def main():
    """Función principal"""
    print("=== Iniciando subida SFTP ===\n")
    
    ssh, sftp = get_sftp_connection(SFTP_CONFIG)
    
    try:
        # 1. Subir archivos
        uploaded = upload_directory(sftp, SFTP_CONFIG['LOCAL_FOLDER'], SFTP_CONFIG['REMOTE_FOLDER'])
        print(f"\nArchivos subidos: {len(uploaded)}")
        
    finally:
        # 2. Cerrar conexión SFTP (liberar recursos)
        sftp.close()
        ssh.close()
        print("\n✓ Conexión SFTP cerrada")
    
    # 3. AHORA sí borrar archivos (después de cerrar SFTP)
    if uploaded:
        print("\n=== Borrando archivos locales ===")
        delete_local_files(SFTP_CONFIG['LOCAL_FOLDER'])
    
    print("\n=== Proceso completado ===")

if __name__ == "__main__":
    main()