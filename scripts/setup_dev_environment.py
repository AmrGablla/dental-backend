#!/usr/bin/env python3
"""Development environment setup script for dental backend."""

import subprocess
import sys
from pathlib import Path


def run_command(command: str, cwd: Path | None = None) -> bool:
    """Run a shell command and return success status."""
    try:
        subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ {command}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {command}")
        print(f"Error: {e.stderr}")
        return False


def check_python_version() -> bool:
    """Check if Python version meets requirements."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("✗ Python 3.10+ is required")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def create_directories() -> None:
    """Create necessary directories."""
    directories = [
        "logs",
        "data",
        "models/trained",
        "models/configs",
        "models/data",
        "tests/unit",
        "tests/integration",
        "docs",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {directory}")


def setup_pre_commit() -> bool:
    """Set up pre-commit hooks."""
    if not run_command("pre-commit install"):
        return False
    return True


def main() -> None:
    """Main setup function."""
    print("Setting up Dental Backend development environment...")
    print("=" * 50)

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Create directories
    print("\nCreating directories...")
    create_directories()

    # Install dependencies
    print("\nInstalling dependencies...")
    if not run_command("pip3 install -r requirements.txt"):
        print("Failed to install production dependencies")
        sys.exit(1)

    if not run_command("pip3 install -r requirements-dev.txt"):
        print("Failed to install development dependencies")
        sys.exit(1)

    # Install packages in development mode
    print("\nInstalling packages in development mode...")
    packages = ["packages/common", "services/api", "services/worker"]
    for package in packages:
        if not run_command("pip3 install -e .", cwd=Path(package)):
            print(f"Failed to install {package}")
            sys.exit(1)

    # Set up pre-commit hooks
    print("\nSetting up pre-commit hooks...")
    if not setup_pre_commit():
        print("Failed to set up pre-commit hooks")
        sys.exit(1)

    # Create .env file if it doesn't exist
    env_file = Path(".env")
    if not env_file.exists():
        print("\nCreating .env file...")
        env_content = """# Database Configuration
DATABASE_URL=postgresql://dental_user:dental_password@localhost:5432/dental_backend

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# S3 Configuration
S3_ENDPOINT_URL=http://localhost:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=dental-scans

# Security
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Logging
LOG_LEVEL=INFO
"""
        env_file.write_text(env_content)
        print("✓ Created .env file")

    print("\n" + "=" * 50)
    print("✓ Development environment setup complete!")
    print("\nNext steps:")
    print("1. Review and update .env file with your configuration")
    print("2. Start services with: make run-all")
    print("3. Run tests with: make test")
    print("4. Check code quality with: make lint")


if __name__ == "__main__":
    main()
