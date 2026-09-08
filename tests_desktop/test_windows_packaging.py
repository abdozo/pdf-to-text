from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_keeps_a_stable_upgrade_identity_and_preserves_user_data():
    installer = (ROOT / "packaging" / "windows" / "Warraq.iss").read_text(encoding="utf-8")

    assert "AppId={{EE07122C-534E-478F-BA57-9ACD25759B8B}" in installer
    assert "UsePreviousAppDir=yes" in installer
    assert "DefaultDirName={autopf}\\Warraq" in installer
    assert "{localappdata}" not in installer.lower()
    assert "uninstalldelete" not in installer.lower()


def test_windows_deployment_is_standalone_and_has_a_windows_icon():
    config = (ROOT / "packaging" / "windows" / "pysidedeploy.spec.in").read_text(encoding="utf-8")

    assert "mode = standalone" in config
    assert "icon = waraq/assets/Warraq.ico" in config
    assert "--windows-console-mode=disable" in config


def test_cloud_workflow_builds_on_windows_and_uploads_the_installer():
    workflow = (ROOT / ".github" / "workflows" / "build-windows.yml").read_text(encoding="utf-8")

    assert "runs-on: windows-latest" in workflow
    assert "scripts\\build_windows.ps1" in workflow
    assert "dist/windows/installer/Warraq-Setup-*.exe" in workflow
    assert "actions/upload-artifact@v4" in workflow
