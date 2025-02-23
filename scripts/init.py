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
    def __init__(self, project_name: str, repo_org: str, repositories: List[Dict]):
        self.project_name = project_name
        self.repo_org = repo_org
        self.repositories = repositories
        self.base_dir = Path("..").resolve()
        self.semaphore = asyncio.Semaphore(5)  # Limit concurrent git operations

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

    async def process_repository(self, repo: Dict) -> None:
        """Process a single repository"""
        async with self.semaphore:
            repo_name = repo["name"]
            repo_path = self.base_dir / repo_name
            expected_remote = f"git@github.com:{self.repo_org}/{repo_name}.git"

            print(f"\nProcessing repository: {repo_name}")

            if repo_path.exists():
                print(f"Repository {repo_name} exists, verifying...")
                if await self.check_remote(repo_path, expected_remote):
                    print(f"Updating {repo_name}...")
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
                else:
                    print(f"❌ Failed to clone {repo_name}")

    async def run(self) -> None:
        """Initialize the project workspace"""
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
    args = parser.parse_args()

    # Project configuration
    config = {
        "project_name": "gcp-kubernetes",
        "repo_org": "HappyPathway",
        "repositories": ["terraform-gcp-compute","terraform-gcp-networking","terraform-gcp-storage","terraform-gcp-monitoring","terraform-gcp-security","gcp-deployment"]
    }

    if args.debug:
        print("Configuration:")
        print(json.dumps(config, indent=2))

    # Run initialization
    initializer = ProjectInitializer(**config)
    asyncio.run(initializer.run())