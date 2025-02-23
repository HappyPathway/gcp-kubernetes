#!/usr/bin/env python3
"""Project initialization script for gcp-kubernetes"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Dict
import aiohttp
import asyncio.subprocess


class ProjectInitializer:
    def __init__(self, project_name: str, repo_org: str, repositories: List[Dict], commit_message: str = None, excluded_repos: List[str] = None, remote_operation: str = None, remote_name: str = None, remote_url: str = None):
        self.project_name = project_name
        self.repo_org = repo_org
        self.repositories = json.loads(repositories)  # Deserialize the JSON string
        self.base_dir = Path("..").resolve()
        self.commit_message = commit_message
        self.excluded_repos = excluded_repos or []
        self.remote_operation = remote_operation
        self.remote_name = remote_name
        self.remote_url = remote_url
        self.semaphore = None # will be created in run() to attach to the proper event loop

    async def verify_git_ssh(self) -> bool:
        """Verify Git SSH access to GitHub"""
        try:
            process = await asyncio.create_subprocess_exec(
                "ssh", "-T", "git@github.com",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            return "successfully authenticated" in stderr.decode().lower()
        except Exception as e:
            print(f"Error verifying Git SSH access: {e}")
            return False

    async def check_remote(self, repo_path: Path, expected_remote: str) -> bool:
        """Check if repository remote matches expected URL"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "remote", "get-url", "origin",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            stdout, _ = await process.communicate()
            current_remote = stdout.decode().strip()
            return current_remote == expected_remote
        except Exception:
            return False

    async def update_repository(self, repo_path: Path) -> bool:
        """Update existing repository"""
        try:
            # Fetch latest changes
            fetch_process = await asyncio.create_subprocess_exec(
                "git", "fetch",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await fetch_process.communicate()

            # Get current branch
            branch_process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            stdout, _ = await branch_process.communicate()
            current_branch = stdout.decode().strip()

            # Pull latest changes
            pull_process = await asyncio.create_subprocess_exec(
                "git", "pull", "origin", current_branch,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await pull_process.communicate()
            return True
        except Exception as e:
            print(f"Error updating repository: {e}")
            return False

    async def clone_repository(self, repo_name: str, repo_path: Path) -> bool:
        """Clone a repository"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "clone",
                f"git@github.com:{self.repo_org}/{repo_name}.git",
                str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return True
        except Exception as e:
            print(f"Error cloning repository: {e}")
            return False

    async def get_current_branch(self, repo_path: Path) -> str:
        """Get the current branch of a repository"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "--abbrev-ref", "HEAD",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            stdout, _ = await process.communicate()
            return stdout.decode().strip()
        except Exception as e:
            print(f"Error getting current branch: {e}")
            return "main"  # Default to main if error

    async def checkout_branch(self, repo_path: Path, branch_name: str) -> str:
        """Checkout a branch in a repository, creating it if it doesn't exist.
        Returns the name of the branch checked out, or None on failure."""
        try:
            # Try to checkout the branch
            process = await asyncio.create_subprocess_exec(
                "git", "checkout", branch_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await process.communicate()
            return branch_name
        except Exception as e:
            # If the branch doesn't exist, create it
            try:
                process = await asyncio.create_subprocess_exec(
                    "git", "checkout", "-b", branch_name, "origin/main",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=repo_path
                )
                await process.communicate()
                return branch_name
            except Exception as e:
                print(f"Error checking out/creating branch {branch_name}: {e}")
                return None

    async def commit_changes(self, repo_path: Path, commit_message: str) -> bool:
        """Commit changes in a repository, allowing empty commits"""
        try:
            # Add all changes
            add_process = await asyncio.create_subprocess_exec(
                "git", "add", ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await add_process.communicate()

            # Commit with the provided message, allowing empty commits
            commit_process = await asyncio.create_subprocess_exec(
                "git", "commit", "-m", commit_message, "--allow-empty",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await commit_process.communicate()
            return True
        except Exception as e:
            print(f"Error committing changes: {e}")
            return False

    async def add_remote(self, repo_path: Path, remote_name: str, remote_url: str) -> bool:
        """Add a remote to the repository"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "remote", "add", remote_name, remote_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await process.communicate()
            return True
        except Exception as e:
            print(f"Error adding remote: {e}")
            return False

    async def update_remote(self, repo_path: Path, remote_name: str, remote_url: str) -> bool:
        """Update a remote in the repository"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "remote", "set-url", remote_name, remote_url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await process.communicate()
            return True
        except Exception as e:
            print(f"Error updating remote: {e}")
            return False

    async def delete_remote(self, repo_path: Path, remote_name: str) -> bool:
        """Delete a remote from the repository"""
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "remote", "remove", remote_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=repo_path
            )
            await process.communicate()
            return True
        except Exception as e:
            print(f"Error deleting remote: {e}")
            return False

    async def process_repository(self, repo: Dict) -> None:
        """Process a single repository"""
        async with self.semaphore:
            repo_name = repo["name"]
            repo_path = self.base_dir / repo_name
            expected_remote = f"git@github.com:{self.repo_org}/{repo_name}.git"

            print(f"\nProcessing repository: {repo_name}")

            # Get the target branch from the current working directory
            current_working_dir = Path(os.getcwd())
            target_branch = await self.get_current_branch(current_working_dir)

            if repo_path.exists():
                print(f"Repository {repo_name} exists, verifying...")
                if await self.check_remote(repo_path, expected_remote):
                    print(f"Updating {repo_name}...")
                    checked_out_branch = await self.checkout_branch(repo_path, target_branch)
                    if checked_out_branch:
                        print(f"✅ {repo_name} checked out to branch {checked_out_branch}")
                    else:
                        print(f"❌ Failed to checkout branch {target_branch} for {repo_name}")
                    if await self.update_repository(repo_path):
                        print(f"✅ {repo_name} updated successfully")
                    else:
                        print(f"❌ Failed to update {repo_name}")
                else:
                    print(f"❌ Remote mismatch for {repo_name}")
                    print(f"Expected: {expected_remote}")
                    print("Please check the repository manually")
            else:
                print(f"Cloning {repo_name}...")
                if await self.clone_repository(repo_name, repo_path):
                    print(f"✅ {repo_name} cloned successfully")
                    checked_out_branch = await self.checkout_branch(repo_path, target_branch)
                    if checked_out_branch:
                        print(f"✅ {repo_name} checked out to branch {checked_out_branch}")
                    else:
                        print(f"❌ Failed to checkout branch {target_branch} for {repo_name}")
                else:
                    print(f"❌ Failed to clone {repo_name}")

            # Manage remote if requested and not excluded
            if self.remote_operation and repo_name not in self.excluded_repos:
                print(f"Managing remote in {repo_name}...")
                # Append repo name to remote URL
                effective_remote_url = f"{self.remote_url}{repo_name}" if self.remote_url else None

                if self.remote_operation == "add":
                    if self.remote_name and effective_remote_url:
                        if await self.add_remote(repo_path, self.remote_name, effective_remote_url):
                            print(f"✅ Added remote {self.remote_name} to {repo_name} with URL {effective_remote_url}")
                        else:
                            print(f"❌ Failed to add remote {self.remote_name} to {repo_name}")
                    else:
                        print("❌ Remote name and URL are required for adding a remote.")
                elif self.remote_operation == "update":
                    if self.remote_name and effective_remote_url:
                        if await self.update_remote(repo_path, self.remote_name, effective_remote_url):
                            print(f"✅ Updated remote {self.remote_name} in {repo_name} with URL {effective_remote_url}")
                        else:
                            print(f"❌ Failed to update remote {self.remote_name} in {repo_name}")
                    else:
                        print("❌ Remote name and URL are required for updating a remote.")
                elif self.remote_operation == "delete":
                    if self.remote_name:
                        if await self.delete_remote(repo_path, self.remote_name):
                            print(f"✅ Deleted remote {self.remote_name} from {repo_name}")
                        else:
                            print(f"❌ Failed to delete remote {self.remote_name} from {repo_name}")
                    else:
                        print("❌ Remote name is required for deleting a remote.")
                else:
                    print(f"❌ Invalid remote operation: {self.remote_operation}")
            
            # Commit changes if requested and not excluded
            if self.commit_message and repo_name not in self.excluded_repos:
                print(f"Committing changes in {repo_name}...")
                if await self.commit_changes(repo_path, self.commit_message):
                    print(f"✅ {repo_name} committed successfully")
                else:
                    print(f"❌ Failed to commit changes in {repo_name}")

    async def run(self) -> None:
        """Initialize the project workspace"""
        self.semaphore = asyncio.Semaphore(5)  # Initialize semaphore
        print(f"Initializing project: {self.project_name}")

        # Create parent directory
        os.makedirs(self.base_dir, exist_ok=True)

        # Verify Git SSH access
        print("\nVerifying Git SSH access to GitHub...")
        if not await self.verify_git_ssh():
            print("❌ Failed to verify Git SSH access to GitHub")
            print("Please check your SSH configuration")
            sys.exit(1)
        print("✅ Git SSH access verified")

        # Process repositories in parallel
        tasks = [self.process_repository(repo) for repo in self.repositories]
        await asyncio.gather(*tasks)

        print("\n✅ Project initialization complete!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Initialize project workspace")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--commit", action="store_true", help="Enable committing changes")
    parser.add_argument("--message", type=str, help="Commit message")
    parser.add_argument("--exclude", nargs="+", type=str, help="List of repositories to exclude from operations")
    parser.add_argument("--remote-operation", type=str, choices=["add", "update", "delete"], help="Remote operation to perform (add, update, delete)")
    parser.add_argument("--remote-name", type=str, help="Remote name")
    parser.add_argument("--remote-url", type=str, help="Remote URL")
    args = parser.parse_args()

    # Project configuration
    config = {
        "project_name": "gcp-kubernetes",
        "repo_org": "HappyPathway",
        "repositories": [{"additional_codeowners":[],"admin_teams":[],"archive_on_destroy":true,"archived":false,"collaborators":{},"create_codeowners":true,"create_repo":true,"enforce_prs":false,"extra_files":[],"force_name":true,"github_allow_merge_commit":false,"github_allow_rebase_merge":false,"github_allow_squash_merge":true,"github_auto_init":true,"github_default_branch":"main","github_delete_branch_on_merge":true,"github_dismiss_stale_reviews":true,"github_enforce_admins_branch_protection":true,"github_has_issues":false,"github_has_projects":true,"github_has_wiki":true,"github_is_private":true,"github_org_teams":null,"github_push_restrictions":[],"github_repo_description":"Repository for the gcp-compute module in gcp-kubernetes","github_repo_topics":["terraform","gcp","networking","security","infrastructure"],"github_require_code_owner_reviews":true,"github_required_approving_review_count":1,"gitignore_template":null,"homepage_url":null,"is_template":false,"managed_extra_files":null,"name":"terraform-gcp-compute","prefix":null,"prompt":"\n# Compute \u0026 Application Module\n\n## Overview\nThis module provisions the Google Kubernetes Engine (GKE) cluster and related resources.\n\n## Resources Created\n- **GKE Cluster**\n- **Node Pools**\n- **Autoscaling Configuration**\n\n## Inputs\n- `project_id` - GCP Project ID\n- `region` - Deployment region\n- `gke_cluster_name` - Name of the GKE Cluster\n- `node_count` - Number of nodes in the pool\n- `machine_type` - Machine type for the nodes\n- `enable_autoscaling` - Boolean to enable autoscaling\n\n## Outputs\n- `gke_cluster_endpoint` - Endpoint for the GKE cluster\n- `node_pool_names` - Names of the node pools\n\n## Usage Example\n```hcl\nmodule \"compute\" {\n  source            = \"./modules/compute\"\n  project_id        = \"my-gcp-project\"\n  region            = \"us-central1\"\n  gke_cluster_name  = \"terraform-ai-cluster\"\n  node_count        = 3\n  machine_type      = \"e2-standard-4\"\n  enable_autoscaling = true\n}\n```\n\n## Best Practices\n- Use **Autopilot mode** for reduced operational overhead.\n- Enable **node auto-repair** and **auto-upgrade**.\n- Restrict public access using **private clusters**.\n","pull_request_bypassers":[],"repo_org":null,"required_status_checks":null,"secrets":[],"security_and_analysis":null,"template_repo":null,"template_repo_org":null,"vars":[],"vulnerability_alerts":false},{"additional_codeowners":[],"admin_teams":[],"archive_on_destroy":true,"archived":false,"collaborators":{},"create_codeowners":true,"create_repo":true,"enforce_prs":false,"extra_files":[],"force_name":true,"github_allow_merge_commit":false,"github_allow_rebase_merge":false,"github_allow_squash_merge":true,"github_auto_init":true,"github_default_branch":"main","github_delete_branch_on_merge":true,"github_dismiss_stale_reviews":true,"github_enforce_admins_branch_protection":true,"github_has_issues":false,"github_has_projects":true,"github_has_wiki":true,"github_is_private":true,"github_org_teams":null,"github_push_restrictions":[],"github_repo_description":"Repository for the gcp-networking module in gcp-kubernetes","github_repo_topics":["terraform","gcp","networking","security","infrastructure"],"github_require_code_owner_reviews":true,"github_required_approving_review_count":1,"gitignore_template":null,"homepage_url":null,"is_template":false,"managed_extra_files":null,"name":"terraform-gcp-networking","prefix":null,"prompt":"\n# Networking \u0026 Security Module\n\n## Overview\nThis module provisions the networking and security components for the AI-powered Terraform module generator infrastructure on GCP.\n\n## Resources Created\n- **VPC \u0026 Subnets**\n- **Firewall Rules**\n- **IAM \u0026 Service Accounts**\n- **Private Google Access**\n- **Cloud NAT** (if needed for outbound traffic)\n\n## Inputs\n- `project_id` - GCP Project ID\n- `region` - Deployment region\n- `vpc_name` - Name of the VPC\n- `subnet_ranges` - CIDR blocks for subnets\n\n## Outputs\n- `vpc_id` - ID of the created VPC\n- `subnet_ids` - List of created subnet IDs\n- `service_account_email` - IAM Service Account Email\n\n## Usage Example\n```hcl\nmodule \"networking\" {\n  source       = \"./modules/networking\"\n  project_id   = \"my-gcp-project\"\n  region       = \"us-central1\"\n  vpc_name     = \"my-vpc\"\n  subnet_ranges = [\"10.0.1.0/24\", \"10.0.2.0/24\"]\n}\n```\n\n## Security Considerations\n- Ensure **least privilege IAM roles** for service accounts.\n- Enable **VPC Service Controls** if needed.\n- Restrict firewall rules to allow only necessary traffic.\n\n## Best Practices\n- Use **private Google access** for secure Cloud SQL connections.\n- Enable **Cloud NAT** if private outbound access is needed.\n","pull_request_bypassers":[],"repo_org":null,"required_status_checks":null,"secrets":[],"security_and_analysis":null,"template_repo":null,"template_repo_org":null,"vars":[],"vulnerability_alerts":false},{"additional_codeowners":[],"admin_teams":[],"archive_on_destroy":true,"archived":false,"collaborators":{},"create_codeowners":true,"create_repo":true,"enforce_prs":false,"extra_files":[],"force_name":true,"github_allow_merge_commit":false,"github_allow_rebase_merge":false,"github_allow_squash_merge":true,"github_auto_init":true,"github_default_branch":"main","github_delete_branch_on_merge":true,"github_dismiss_stale_reviews":true,"github_enforce_admins_branch_protection":true,"github_has_issues":false,"github_has_projects":true,"github_has_wiki":true,"github_is_private":true,"github_org_teams":null,"github_push_restrictions":[],"github_repo_description":"Repository for the gcp-storage module in gcp-kubernetes","github_repo_topics":["terraform","gcp","storage","database","infrastructure"],"github_require_code_owner_reviews":true,"github_required_approving_review_count":1,"gitignore_template":null,"homepage_url":null,"is_template":false,"managed_extra_files":null,"name":"terraform-gcp-storage","prefix":null,"prompt":"\n# Data \u0026 Storage Module\n\n## Overview\nThis module provisions Cloud SQL for PostgreSQL and Cloud Storage for Terraform module uploads.\n\n## Resources Created\n- **Cloud SQL (PostgreSQL)**\n- **Cloud Storage Bucket**\n- **IAM Permissions for Secure Access**\n- **Backup \u0026 PITR Configurations**\n\n## Inputs\n- `project_id` - GCP Project ID\n- `region` - Deployment region\n- `db_instance_name` - Name of the Cloud SQL instance\n- `db_tier` - Machine type for Cloud SQL\n- `storage_bucket_name` - Name of the storage bucket\n\n## Outputs\n- `db_instance_connection_name` - Connection name for Cloud SQL\n- `storage_bucket_url` - URL of the storage bucket\n\n## Usage Example\n```hcl\nmodule \"storage\" {\n  source               = \"./modules/storage\"\n  project_id           = \"my-gcp-project\"\n  region               = \"us-central1\"\n  db_instance_name     = \"terraform-db\"\n  db_tier              = \"db-custom-1-3840\"\n  storage_bucket_name  = \"terraform-modules-bucket\"\n}\n```\n\n## Best Practices\n- Use **Cloud SQL Auth Proxy** instead of public IP access.\n- Enable **Automated Backups \u0026 PITR**.\n- Set appropriate IAM roles for bucket access.\n","pull_request_bypassers":[],"repo_org":null,"required_status_checks":null,"secrets":[],"security_and_analysis":null,"template_repo":null,"template_repo_org":null,"vars":[],"vulnerability_alerts":false},{"additional_codeowners":[],"admin_teams":[],"archive_on_destroy":true,"archived":false,"collaborators":{},"create_codeowners":true,"create_repo":true,"enforce_prs":false,"extra_files":[],"force_name":true,"github_allow_merge_commit":false,"github_allow_rebase_merge":false,"github_allow_squash_merge":true,"github_auto_init":true,"github_default_branch":"main","github_delete_branch_on_merge":true,"github_dismiss_stale_reviews":true,"github_enforce_admins_branch_protection":true,"github_has_issues":false,"github_has_projects":true,"github_has_wiki":true,"github_is_private":true,"github_org_teams":null,"github_push_restrictions":[],"github_repo_description":"Repository for the gcp-monitoring module in gcp-kubernetes","github_repo_topics":["terraform","gcp","storage","database","infrastructure","networking"],"github_require_code_owner_reviews":true,"github_required_approving_review_count":1,"gitignore_template":null,"homepage_url":null,"is_template":false,"managed_extra_files":null,"name":"terraform-gcp-monitoring","prefix":null,"prompt":"\n# Data \u0026 Storage Module\n\n## Overview\nThis module provisions Cloud SQL for PostgreSQL and Cloud Storage for Terraform module uploads.\n\n## Resources Created\n- **Cloud SQL (PostgreSQL)**\n- **Cloud Storage Bucket**\n- **IAM Permissions for Secure Access**\n- **Backup \u0026 PITR Configurations**\n\n## Inputs\n- `project_id` - GCP Project ID\n- `region` - Deployment region\n- `db_instance_name` - Name of the Cloud SQL instance\n- `db_tier` - Machine type for Cloud SQL\n- `storage_bucket_name` - Name of the storage bucket\n\n## Outputs\n- `db_instance_connection_name` - Connection name for Cloud SQL\n- `storage_bucket_url` - URL of the storage bucket\n\n## Usage Example\n```hcl\nmodule \"storage\" {\n  source               = \"./modules/storage\"\n  project_id           = \"my-gcp-project\"\n  region               = \"us-central1\"\n  db_instance_name     = \"terraform-db\"\n  db_tier              = \"db-custom-1-3840\"\n  storage_bucket_name  = \"terraform-modules-bucket\"\n}\n```\n\n## Best Practices\n- Use **Cloud SQL Auth Proxy** instead of public IP access.\n- Enable **Automated Backups \u0026 PITR**.\n- Set appropriate IAM roles for bucket access.\n","pull_request_bypassers":[],"repo_org":null,"required_status_checks":null,"secrets":[],"security_and_analysis":null,"template_repo":null,"template_repo_org":null,"vars":[],"vulnerability_alerts":false},{"additional_codeowners":[],"admin_teams":[],"archive_on_destroy":true,"archived":false,"collaborators":{},"create_codeowners":true,"create_repo":true,"enforce_prs":false,"extra_files":[],"force_name":true,"github_allow_merge_commit":false,"github_allow_rebase_merge":false,"github_allow_squash_merge":true,"github_auto_init":true,"github_default_branch":"main","github_delete_branch_on_merge":true,"github_dismiss_stale_reviews":true,"github_enforce_admins_branch_protection":true,"github_has_issues":false,"github_has_projects":true,"github_has_wiki":true,"github_is_private":true,"github_org_teams":null,"github_push_restrictions":[],"github_repo_description":"Repository for the gcp-security module in gcp-kubernetes","github_repo_topics":["terraform","gcp","security","networking","infrastructure"],"github_require_code_owner_reviews":true,"github_required_approving_review_count":1,"gitignore_template":null,"homepage_url":null,"is_template":false,"managed_extra_files":null,"name":"terraform-gcp-security","prefix":null,"prompt":"# Security Module for GCP Infrastructure\n\n## Overview\nThis module implements security controls specifically for a GKE-based infrastructure with Cloud SQL and Cloud Storage components, focusing on containerized workload security, data protection, and compliance.\n\n## Key Security Components\n\n### Kubernetes Security\n- **GKE Security Controls**\n  - Node pool security hardening\n  - Workload Identity configuration\n  - Pod security policies\n  - Network policies\n  - Binary Authorization\n  - Container-Optimized OS\n\n### Database Security\n- **Cloud SQL Protection**\n  - Cloud SQL Auth Proxy implementation\n  - Database encryption (CMEK)\n  - SSL/TLS enforcement\n  - Private IP configuration\n  - Automated backups and PITR\n  - Instance IAM authentication\n\n### Storage Security\n- **Cloud Storage Controls**\n  - Bucket-level encryption\n  - Object versioning\n  - Lifecycle policies\n  - IAM conditions for access\n  - VPC Service Controls\n  - Object level logging\n\n### Network Security\n- **VPC \u0026 Ingress Protection**\n  - Private GKE clusters\n  - Cloud Armor policies\n  - Load balancer security\n  - Cloud NAT configuration\n  - VPC service controls\n  - Internal load balancing\n\n## Required Variables\n```hcl\nvariable \"project_id\" {\n  description = \"GCP Project ID\"\n  type        = string\n}\n\nvariable \"region\" {\n  description = \"Primary deployment region\"\n  type        = string\n}\n\nvariable \"gke_security_config\" {\n  description = \"GKE security configuration settings\"\n  type = object({\n    enable_workload_identity    = bool\n    enable_binary_authorization = bool\n    pod_security_policy        = bool\n    enable_network_policy      = bool\n  })\n  default = {\n    enable_workload_identity    = true\n    enable_binary_authorization = true\n    pod_security_policy        = true\n    enable_network_policy      = true\n  }\n}\n\nvariable \"database_security_config\" {\n  description = \"Cloud SQL security configuration\"\n  type = object({\n    require_ssl        = bool\n    private_network   = bool\n    backup_enabled    = bool\n    point_in_time_recovery = bool\n  })\n  default = {\n    require_ssl        = true\n    private_network   = true\n    backup_enabled    = true\n    point_in_time_recovery = true\n  }\n}\n```\n\n## Security Best Practices\n\n### 1. Kubernetes Workload Security\n- Use Workload Identity for pod authentication\n- Implement pod security policies\n- Enable network policies for pod isolation\n- Configure node auto-upgrade\n- Use Container-Optimized OS\n- Regular vulnerability scanning\n\n### 2. Data Security\n- Enable Cloud SQL Auth Proxy\n- Implement end-to-end encryption\n- Use CMEK for sensitive data\n- Enable audit logging\n- Regular backup verification\n- Data classification and DLP\n\n### 3. Network Security\n- Private GKE clusters only\n- Cloud Armor for DDoS protection\n- SSL/TLS termination at load balancer\n- Internal load balancing where possible\n- VPC service controls for data boundaries\n\n## Usage Example\n```hcl\nmodule \"security\" {\n  source = \"./modules/security\"\n  \n  project_id = \"my-gcp-project\"\n  region     = \"us-central1\"\n  \n  gke_security_config = {\n    enable_workload_identity    = true\n    enable_binary_authorization = true\n    pod_security_policy        = true\n    enable_network_policy      = true\n  }\n  \n  database_security_config = {\n    require_ssl             = true\n    private_network        = true\n    backup_enabled         = true\n    point_in_time_recovery = true\n  }\n}\n```\n\n## Security Monitoring \u0026 Alerts\n- GKE cluster security posture\n- Database access patterns\n- Storage access logs\n- Network traffic analysis\n- IAM policy changes\n- Workload Identity usage\n\n## Outputs\n```hcl\noutput \"security_policy_id\" {\n  description = \"Cloud Armor security policy ID\"\n  value       = module.security.security_policy_id\n}\n\noutput \"network_policy_status\" {\n  description = \"Network policy enablement status\"\n  value       = module.security.network_policy_status\n}\n\noutput \"workload_identity_config\" {\n  description = \"Workload Identity configuration\"\n  value       = module.security.workload_identity_config\n}\n```\n\n## Regular Security Tasks\n- GKE version upgrades\n- Node pool rotation\n- SSL certificate rotation\n- Security posture review\n- Access review and cleanup\n- Vulnerability scanning","pull_request_bypassers":[],"repo_org":null,"required_status_checks":null,"secrets":[],"security_and_analysis":null,"template_repo":null,"template_repo_org":null,"vars":[],"vulnerability_alerts":false},{"additional_codeowners":[],"admin_teams":[],"archive_on_destroy":true,"archived":false,"collaborators":{},"create_codeowners":true,"create_repo":true,"enforce_prs":false,"extra_files":[],"force_name":true,"github_allow_merge_commit":false,"github_allow_rebase_merge":false,"github_allow_squash_merge":true,"github_auto_init":true,"github_default_branch":"main","github_delete_branch_on_merge":true,"github_dismiss_stale_reviews":true,"github_enforce_admins_branch_protection":true,"github_has_issues":false,"github_has_projects":true,"github_has_wiki":true,"github_is_private":true,"github_org_teams":null,"github_push_restrictions":[],"github_repo_description":"Repository for the gcp-deployment module in gcp-kubernetes","github_repo_topics":["terraform","workspace","gcp","deployment","infrastructure"],"github_require_code_owner_reviews":true,"github_required_approving_review_count":1,"gitignore_template":null,"homepage_url":null,"is_template":false,"managed_extra_files":null,"name":"gcp-deployment","prefix":null,"prompt":"# Deployment Module for GCP Infrastructure\n\n## Overview\nThis module manages the deployment of core infrastructure services to GKE using Terraform with ArgoCD and Helm providers. It provides a GitOps-based approach to managing Kubernetes resources while maintaining the benefits of Terraform state management.\n\n## Module Structure\n```\ndeployment/\n├── main.tf\n├── variables.tf\n├── outputs.tf\n├── versions.tf\n├── providers.tf\n└── helm/\n    ├── argocd/\n    │   ├── values.yaml\n    │   └── applications/\n    │       ├── monitoring.yaml\n    │       ├── logging.yaml\n    │       └── security.yaml\n    └── core-services/\n        ├── cert-manager/\n        ├── external-dns/\n        └── ingress-nginx/\n```\n\n## Key Components\n\n### ArgoCD Setup\n- ArgoCD installation and configuration via Helm\n- Application-of-Applications pattern\n- RBAC and SSO integration\n- Private repository authentication\n- Automated sync policies\n\n### Core Infrastructure Services\n- Certificate management (cert-manager)\n- DNS management (external-dns)\n- Ingress controller (nginx)\n- Monitoring stack (Prometheus/Grafana)\n- Logging solution (Loki/Promtail)\n\n### GitOps Workflow\n- Git repository structure\n- Application definitions\n- Sync policies\n- Health checks\n- Rollback procedures\n\n## Required Variables\n```hcl\nvariable \"project_id\" {\n  description = \"GCP Project ID\"\n  type        = string\n}\n\nvariable \"region\" {\n  description = \"GCP Region\"\n  type        = string\n}\n\nvariable \"cluster_name\" {\n  description = \"GKE cluster name\"\n  type        = string\n}\n\nvariable \"argocd_config\" {\n  description = \"ArgoCD configuration settings\"\n  type = object({\n    version           = string\n    repo_url          = string\n    target_revision   = string\n    namespace         = string\n    create_namespace  = bool\n  })\n  default = {\n    version           = \"latest\"\n    repo_url          = \"\"\n    target_revision   = \"HEAD\"\n    namespace         = \"argocd\"\n    create_namespace  = true\n  }\n}\n\nvariable \"helm_releases\" {\n  description = \"List of Helm releases to deploy\"\n  type = list(object({\n    name       = string\n    repository = string\n    chart      = string\n    version    = string\n    namespace  = string\n    values     = map(any)\n  }))\n}\n```\n\n## Usage Example\n```hcl\nmodule \"deployment\" {\n  source = \"./modules/deployment\"\n  \n  project_id   = \"my-gcp-project\"\n  region       = \"us-central1\"\n  cluster_name = \"my-gke-cluster\"\n  \n  argocd_config = {\n    version          = \"2.8.0\"\n    repo_url         = \"git@github.com:myorg/k8s-manifests.git\"\n    target_revision  = \"main\"\n    namespace        = \"argocd\"\n    create_namespace = true\n  }\n  \n  helm_releases = [\n    {\n      name       = \"cert-manager\"\n      repository = \"https://charts.jetstack.io\"\n      chart      = \"cert-manager\"\n      version    = \"v1.12.0\"\n      namespace  = \"cert-manager\"\n      values     = {\n        installCRDs = true\n      }\n    },\n    {\n      name       = \"ingress-nginx\"\n      repository = \"https://kubernetes.github.io/ingress-nginx\"\n      chart      = \"ingress-nginx\"\n      version    = \"4.7.0\"\n      namespace  = \"ingress-nginx\"\n      values     = {\n        controller = {\n          service = {\n            type = \"LoadBalancer\"\n          }\n        }\n      }\n    }\n  ]\n}\n```\n\n## Provider Configuration\n```hcl\nterraform {\n  required_providers {\n    helm = {\n      source  = \"hashicorp/helm\"\n      version = \"~\u003e 2.10.0\"\n    }\n    kubernetes = {\n      source  = \"hashicorp/kubernetes\"\n      version = \"~\u003e 2.22.0\"\n    }\n    argocd = {\n      source  = \"oboukili/argocd\"\n      version = \"~\u003e 5.0\"\n    }\n  }\n}\n```\n\n## Outputs\n```hcl\noutput \"argocd_admin_password\" {\n  description = \"ArgoCD admin password\"\n  value       = module.argocd.admin_password\n  sensitive   = true\n}\n\noutput \"argocd_url\" {\n  description = \"ArgoCD server URL\"\n  value       = module.argocd.server_url\n}\n\noutput \"installed_helm_releases\" {\n  description = \"List of installed Helm releases\"\n  value       = module.helm_releases[*].metadata\n}\n```\n\n## Best Practices\n\n### 1. GitOps Implementation\n- Use Application-of-Applications pattern\n- Implement proper RBAC\n- Enable automated sync policies\n- Configure health checks\n- Set up notifications\n\n### 2. Helm Chart Management\n- Version pin all charts\n- Use values files for configuration\n- Implement proper upgrade strategies\n- Configure resource limits\n- Enable monitoring and alerts\n\n### 3. Security Considerations\n- Use HTTPS endpoints\n- Implement network policies\n- Configure RBAC properly\n- Enable audit logging\n- Secure sensitive values\n\n## Regular Maintenance Tasks\n- Chart version updates\n- Security patch application\n- Configuration sync verification\n- Health check validation\n- Backup verification\n- Resource optimization","pull_request_bypassers":[],"repo_org":null,"required_status_checks":null,"secrets":[],"security_and_analysis":null,"template_repo":null,"template_repo_org":null,"vars":[],"vulnerability_alerts":false}]
    }

    if args.debug:
        print("Configuration:")
        print(json.dumps(config, indent=2))

    async def main_async():
        initializer = ProjectInitializer(
            **config,
            commit_message=args.message if args.commit else None,
            excluded_repos=args.exclude if args.exclude else [],
            remote_operation=args.remote_operation,
            remote_name=args.remote_name,
            remote_url=args.remote_url
        )
        await initializer.run()

    asyncio.run(main_async())


if __name__ == "__main__":
    main()