#!/usr/bin/env python
"""
Verification script to check Project Hermes installation.

Run this after installing dependencies to verify everything is set up correctly.
"""

import sys
from pathlib import Path


def check_python_version():
    """Check Python version is 3.9+."""
    print("Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 9:
        print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  ✗ Python {version.major}.{version.minor}.{version.micro} (need 3.9+)")
        return False


def check_dependencies():
    """Check required dependencies are installed."""
    print("\nChecking dependencies...")

    required = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "networkx",
        "osmnx",
        "geopy",
        "shapely",
        "gpxpy",
        "loguru",
        "pytest"
    ]

    all_ok = True
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (not installed)")
            all_ok = False

    return all_ok


def check_project_structure():
    """Check project structure is correct."""
    print("\nChecking project structure...")

    required_dirs = [
        "app",
        "app/api",
        "app/models",
        "app/services",
        "app/core",
        "app/utils",
        "data",
        "tests",
        "scripts",
        "docs"
    ]

    all_ok = True
    for dir_path in required_dirs:
        if Path(dir_path).exists():
            print(f"  ✓ {dir_path}/")
        else:
            print(f"  ✗ {dir_path}/ (missing)")
            all_ok = False

    return all_ok


def check_config_files():
    """Check configuration files exist."""
    print("\nChecking configuration files...")

    required_files = [
        ".env.example",
        "requirements.txt",
        "README.md",
        "data/areas.json"
    ]

    all_ok = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} (missing)")
            all_ok = False

    return all_ok


def check_env_file():
    """Check if .env file exists."""
    print("\nChecking environment configuration...")

    if Path(".env").exists():
        print("  ✓ .env file exists")
        return True
    else:
        print("  ⚠ .env file not found")
        print("    Run: cp .env.example .env")
        return False


def check_app_imports():
    """Check app modules can be imported."""
    print("\nChecking app modules...")

    try:
        from app.config import settings
        print(f"  ✓ app.config")

        from app.models.domain import Node, Route
        print(f"  ✓ app.models.domain")

        from app.services.graph_service import GraphService
        print(f"  ✓ app.services.graph_service")

        from app.core.time_estimators import TimeEstimator
        print(f"  ✓ app.core.time_estimators")

        return True

    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        return False


def check_fastapi_app():
    """Check FastAPI app can be created."""
    print("\nChecking FastAPI application...")

    try:
        from app.main import app
        print(f"  ✓ FastAPI app created")
        print(f"  ✓ App name: {app.title}")
        print(f"  ✓ Routes: {len(app.routes)}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to create app: {e}")
        return False


def print_summary(checks):
    """Print summary of checks."""
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)

    passed = sum(checks.values())
    total = len(checks)

    for check_name, result in checks.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {check_name}")

    print("=" * 60)
    print(f"Result: {passed}/{total} checks passed")

    if passed == total:
        print("\n✅ Installation verified! You're ready to go.")
        print("\nNext steps:")
        print("  1. Start server: uvicorn app.main:app --reload")
        print("  2. Visit: http://localhost:8000/docs")
        print("  3. See QUICKSTART.md for your first route")
    else:
        print("\n⚠️  Some checks failed. Please review the output above.")
        if not checks.get("Environment file"):
            print("\nQuick fix: cp .env.example .env")
        if not checks.get("Dependencies"):
            print("\nQuick fix: pip install -r requirements.txt")

    print("=" * 60)


def main():
    """Run all verification checks."""
    print("=" * 60)
    print("PROJECT HERMES - INSTALLATION VERIFICATION")
    print("=" * 60)

    checks = {
        "Python version": check_python_version(),
        "Dependencies": check_dependencies(),
        "Project structure": check_project_structure(),
        "Config files": check_config_files(),
        "Environment file": check_env_file(),
        "App imports": check_app_imports(),
        "FastAPI app": check_fastapi_app()
    }

    print_summary(checks)

    return all(checks.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
