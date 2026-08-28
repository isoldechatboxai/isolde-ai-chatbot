from pathlib import Path


def test_container_entrypoint_runs_migrations_before_gunicorn():
    root = Path(__file__).resolve().parents[1]
    entrypoint = (root / "docker-entrypoint.sh").read_text(encoding="utf-8")
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "python -m flask db upgrade" in entrypoint
    assert "SKIP_DB_MIGRATE" in entrypoint
    assert "ENTRYPOINT [\"/app/docker-entrypoint.sh\"]" in dockerfile


def test_deployment_documentation_covers_single_and_multi_replica_migrations():
    root = Path(__file__).resolve().parents[1]
    documentation = (root / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "SKIP_DB_MIGRATE=1" in documentation
    assert "CI/CD migration step" in documentation
