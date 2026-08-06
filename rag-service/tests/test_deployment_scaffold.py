from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_phase_10a_deployment_scaffold_files_exist():
    expected_paths = [
        "backend/Dockerfile",
        "rag-service/Dockerfile",
        "compose.yaml",
        "scripts/rag-backfill.sh",
        "scripts/rag-reindex.sh",
        "scripts/rag-retention.sh",
    ]

    for relative_path in expected_paths:
        assert (REPO_ROOT / relative_path).exists(), relative_path


def test_compose_runs_only_local_services():
    compose = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")

    assert "dynamodb-local:" in compose
    assert "backend:" in compose
    assert "rag-service:" in compose
    assert "amazon/dynamodb-local" in compose
    assert "RAG_SERVICE_BASE_URL: ${RAG_SERVICE_BASE_URL:-http://rag-service:8001}" in compose


def test_cloud_deployment_scaffold_is_not_required_for_local_only_deploy():
    cloud_paths = [
        "deploy/terraform/eks-auto-mode/main.tf",
        "deploy/k8s/base/kustomization.yaml",
        "scripts/ecr-publish.sh",
    ]

    for relative_path in cloud_paths:
        assert not (REPO_ROOT / relative_path).exists(), relative_path


def test_ops_policies_do_not_contain_secret_values():
    secret_policy = (REPO_ROOT / "ops/secret-policy.yml").read_text(encoding="utf-8")

    assert "OPENAI_API_KEY" in secret_policy
    assert "sk-" not in secret_policy
