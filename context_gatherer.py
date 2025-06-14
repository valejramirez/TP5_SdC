import os
import subprocess

# --- Configuración ---
OUTPUT_FILENAME = "project_context.md"
FILES_TO_INCLUDE_EXTENSIONS = ['.c', '.py', '.h', '.html', '.css']
FILES_TO_INCLUDE_NAMES = ['Makefile', 'requirements.txt'] # Archivos a incluir por nombre exacto
DIRS_TO_IGNORE = ['legacy', '.git', '__pycache__'] # Directorios a ignorar completamente
FILES_TO_IGNORE = ['context_gatherer.py', 'PATHS.py'] # Archivos a ignorar explícitamente

# --- Funciones Auxiliares ---

def get_tree_output():
    """Ejecuta 'tree --gitignore' y devuelve la salida o un mensaje de error."""
    try:
        # Usamos --gitignore para respetar las reglas de .gitignore
        # -I 'context_gatherer.py|PATHS.py|legacy' es un filtro adicional para asegurar que se ignoren
        # aunque no estén en .gitignore
        command = [
            "tree",
            "--gitignore",
            "-I", "context_gatherer.py|PATHS.py|legacy"
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        return result.stdout
    except FileNotFoundError:
        return "ADVERTENCIA: El comando 'tree' no está instalado. No se pudo generar la estructura de directorios."
    except subprocess.CalledProcessError as e:
        return f"ERROR: El comando 'tree' falló con el siguiente error:\n{e.stderr}"

def get_file_language(filepath):
    """Determina el lenguaje para el bloque de código de Markdown."""
    _, extension = os.path.splitext(filepath)
    filename = os.path.basename(filepath)

    if filename == 'Makefile':
        return 'makefile'
    if extension == '.py':
        return 'python'
    if extension in ['.c', '.h']:
        return 'c'
    if filename == 'requirements.txt':
        return 'text'
    return '' # Lenguaje no especificado

def should_process_file(dirpath, filename):
    """Verifica si un archivo debe ser procesado según las reglas de inclusión/exclusión."""
    if filename in FILES_TO_IGNORE:
        return False

    _, extension = os.path.splitext(filename)
    if filename in FILES_TO_INCLUDE_NAMES or extension in FILES_TO_INCLUDE_EXTENSIONS:
        return True

    return False

def write_files_to_markdown(md_file, title, file_list, project_root):
    """Escribe una sección y su lista de archivos en el archivo Markdown."""
    if not file_list:
        return

    md_file.write(f"# {title}\n\n")
    # Ordenamos la lista para un resultado consistente
    for filepath in sorted(file_list):
        relative_path = os.path.relpath(filepath, project_root)
        language = get_file_language(filepath)

        md_file.write(f"### `{relative_path}`\n\n")
        md_file.write(f"```{language}\n")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                md_file.write(f.read())
        except Exception as e:
            md_file.write(f"Error al leer el archivo: {e}")
        md_file.write("\n```\n\n")

# --- Lógica Principal ---

def main():
    """
    Función principal que recorre el proyecto y genera el archivo Markdown.
    """
    project_root = os.getcwd()
    viewer_files = []
    generator_files = []
    other_files = []

    print("Iniciando recolección de archivos del proyecto...")

    for dirpath, dirnames, filenames in os.walk(project_root, topdown=True):
        # Modificamos 'dirnames' en el lugar para evitar que os.walk entre en estos directorios
        dirnames[:] = [d for d in dirnames if d not in DIRS_TO_IGNORE]

        for filename in filenames:
            if not should_process_file(dirpath, filename):
                continue

            full_path = os.path.join(dirpath, filename)
            # Normalizamos el path para que funcione en cualquier SO (e.g., cambia \ por /)
            normalized_path = full_path.replace(os.sep, '/')

            if 'src/signal_viewer' in normalized_path:
                viewer_files.append(full_path)
            elif 'src/signal_generator' in normalized_path:
                generator_files.append(full_path)
            else:
                # Archivos en la raíz u otras ubicaciones
                other_files.append(full_path)

    print(f"Archivos encontrados: {len(viewer_files)} (Viewer), {len(generator_files)} (Generator), {len(other_files)} (Otros).")

    # Generar el archivo Markdown
    with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as md_file:
        # 1. Consigna
        md_file.write("## Consigna\n\n")
        md_file.write("*(PEGAR AQUÍ LA CONSIGNA ORIGINAL DEL TRABAJO PRÁCTICO)*\n\n")

        # 2. Estructura de directorios (tree)
        md_file.write("## Estructura del Proyecto (generado con `tree`)\n\n")
        md_file.write("```\n")
        md_file.write(get_tree_output())
        md_file.write("\n```\n\n")
        
        # 3. Contenido de los archivos, organizados por módulo
        print("Escribiendo contenido en el archivo Markdown...")

        # Los archivos "otros" suelen ser de configuración a nivel de proyecto.
        # Es bueno ponerlos primero para dar contexto general.
        write_files_to_markdown(md_file, "Archivos de Configuración Raíz", other_files, project_root)
        
        write_files_to_markdown(md_file, "Signal Generator", generator_files, project_root)
        
        write_files_to_markdown(md_file, "Signal Viewer", viewer_files, project_root)

    print(f"¡Listo! Se ha generado el archivo '{OUTPUT_FILENAME}' con todo el contexto del proyecto.")


if __name__ == "__main__":
    main()
