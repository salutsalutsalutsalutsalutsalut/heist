import os

def count_lines_in_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return sum(1 for line in file if line.strip() and not line.strip().startswith('#'))

def count_lines_in_directory(directory):
    total_lines = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                total_lines += count_lines_in_file(file_path)
    return total_lines

def get_loaded_modules(directory):
    loaded_modules = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py') and file != '__init__.py':
                module_name = os.path.splitext(file)[0]
                loaded_modules.append(module_name)
    return loaded_modules