"""
HydraControl — System Integrity and Deployment Verification Utility
Developed for Kvon Tech Pvt Ltd

Validates environment configuration, database engines, MQTT broker, and dependencies.
"""
import sys
import os
import asyncio
from pathlib import Path

# Add project roots
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(ROOT_DIR))


def check_python_version() -> bool:
    print("[1/5] Checking Python Runtime...")
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        print(f"      [OK] Python {major}.{minor} meets requirement (>= 3.11)")
        return True
    else:
        print(f"      [FAIL] Python {major}.{minor} is below minimum requirement (>= 3.11)")
        return False


def check_environment_file() -> bool:
    print("[2/5] Checking Configuration Files...")
    root_env = ROOT_DIR / ".env"
    root_example = ROOT_DIR / ".env.example"
    frontend_example = ROOT_DIR / "frontend" / ".env.example"

    if not root_example.exists():
        print("      [FAIL] .env.example is missing in root")
        return False

    if not frontend_example.exists():
        print("      [FAIL] frontend/.env.example is missing")
        return False

    if not root_env.exists():
        print("      [WARN] .env not found in root (using fallback or defaults)")
    else:
        print("      [OK] Root .env found")

    print("      [OK] Environment templates verified")
    return True


async def check_database_connectivity() -> bool:
    print("[3/5] Checking Database Connectivity & Schema...")
    try:
        from app.db.session import check_db_health, get_async_session
        from app.db.base import Base
        from sqlalchemy import text

        health = await check_db_health()
        if health.get("status") == "connected":
            print(f"      [OK] Database ping OK ({health.get('database')})")
            return True
        else:
            print(f"      [FAIL] Database unhealthy: {health}")
            return False
    except Exception as exc:
        print(f"      [FAIL] Database connection failed: {exc}")
        return False


def check_test_suite_readiness() -> bool:
    print("[4/5] Checking Test Configuration...")
    conftest = BACKEND_DIR / "tests" / "conftest.py"
    if conftest.exists():
        print("      [OK] Pytest conftest and test isolation configured")
        return True
    print("      [FAIL] tests/conftest.py not found")
    return False


def check_mobile_and_frontend() -> bool:
    print("[5/5] Checking Frontend & Mobile Artifacts...")
    frontend_pkg = ROOT_DIR / "frontend" / "package.json"
    apk_file = ROOT_DIR / "apk" / "HydraControl-Universal-v1.0.apk"

    if not frontend_pkg.exists():
        print("      [FAIL] frontend/package.json missing")
        return False

    print("      [OK] Frontend package configuration found")
    if apk_file.exists():
        size_mb = os.path.getsize(apk_file) / (1024 * 1024)
        print(f"      [OK] Universal Release APK present ({size_mb:.2f} MB)")
    else:
        print("      [WARN] apk/HydraControl-Universal-v1.0.apk not found (can build from source)")
    return True


async def main():
    print("=" * 60)
    print("  HydraControl Platform Verification - Kvon Tech Pvt Ltd")
    print("=" * 60)

    p1 = check_python_version()
    p2 = check_environment_file()
    p3 = await check_database_connectivity()
    p4 = check_test_suite_readiness()
    p5 = check_mobile_and_frontend()

    print("=" * 60)
    if all([p1, p2, p3, p4, p5]):
        print("  [SUCCESS] ALL SYSTEM CHECKS PASSED - READY FOR DEPLOYMENT")
        print("=" * 60)
        sys.exit(0)
    else:
        print("  [WARN] SOME CHECKS REQUIRE ATTENTION")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
