import os
import subprocess
import sys

def run_command(command):
    """Run a command and return the result"""
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {command}")
        print(f"Error: {e.stderr}")
        sys.exit(1)

def main():
    print("🚀 Starting SheetToGmail Pro Deployment")
    print("=" * 50)
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Please activate your virtual environment first")
        sys.exit(1)
    
    # Install requirements
    print("📦 Installing requirements...")
    run_command("pip install -r requirements.txt")
    
    # Initialize database
    print("🗄️  Setting up database...")
    run_command("flask db init")
    run_command("flask db migrate -m 'Initial migration'")
    run_command("flask db upgrade")
    
    print("✅ Deployment setup completed!")
    print("\nNext steps:")
    print("1. Set up your hosting platform (Render, PythonAnywhere, etc.)")
    print("2. Configure environment variables")
    print("3. Deploy your application")
    print("4. Set up a custom domain (optional)")

if __name__ == "__main__":
    main()