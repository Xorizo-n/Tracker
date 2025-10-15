import os
import subprocess
import sys

def build_with_debug():
    print("🔨 Сборка приложения с отладочной консолью...")
    
    # Команда сборки С консолью
    cmd = [
        'pyinstaller',
        '--onefile',
        '--add-data', 'templates;templates' if os.name == 'nt' else 'templates:templates',
        '--add-data', 'static;static' if os.name == 'nt' else 'static:static', 
        '--add-data', '.env;.' if os.name == 'nt' else '.env:.',
        '--add-data', 'credentials.json;.' if os.name == 'nt' else 'credentials.json:.',
        '--console',  # ВАЖНО: включаем консоль!
        '--name', 'DutySchedule_Debug',
        'main.py'
    ]
    
    try:
        subprocess.check_call(cmd)
        print("✅ Сборка завершена!")
        print("📁 Исполняемый файл: dist/DutySchedule_Debug.exe")
        print("💡 При запуске откроется консоль с логами")
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка сборки: {e}")

if __name__ == "__main__":
    build_with_debug()