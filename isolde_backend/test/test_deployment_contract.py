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


def test_multi_replica_kubernetes_deployment_skips_pod_startup_migrations():
    root = Path(__file__).resolve().parents[1]
    manifest = (root / "k8s" / "deployment.yaml").read_text(encoding="utf-8")
    assert "replicas: 3" in manifest
    assert "name: SKIP_DB_MIGRATE" in manifest
    assert 'value: "1"' in manifest


def test_docker_build_context_excludes_secrets_and_runtime_data():
    root = Path(__file__).resolve().parents[1]
    dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
    for excluded_path in (".env", "uploads/", "vector_store/", "*.db"):
        assert excluded_path in dockerignore
