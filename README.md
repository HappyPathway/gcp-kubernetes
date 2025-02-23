# gcp-kubernetes

Repository for the gcp-kubernetes project in HappyPathway

## Getting Started

1. Clone this repository:
```bash
git clone git@github.com:HappyPathway/gcp-kubernetes.git
cd gcp-kubernetes
```

2. Set up Python environment and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
pip install -r scripts/requirements.txt
```

3. Run the initialization script:
```bash
python scripts/init.py
```

This will:
- Verify Git SSH access to GitHub
- Create the workspace directory structure
- Clone or update all project repositories
- Set up repository configurations

For debugging, you can run:
```bash
python scripts/init.py --debug
```

## Repository Structure

This project consists of multiple repositories:

- terraform-gcp-compute: gcp-kubernetes::terraform-gcp-compute
- terraform-gcp-networking: gcp-kubernetes::terraform-gcp-networking
- terraform-gcp-storage: gcp-kubernetes::terraform-gcp-storage
- terraform-gcp-monitoring: gcp-kubernetes::terraform-gcp-monitoring
- terraform-gcp-security: gcp-kubernetes::terraform-gcp-security
- gcp-deployment: gcp-kubernetes::gcp-deployment

## Development Environment

This repository includes:
- VS Code workspace configuration
- GitHub Copilot settings
- Project-specific documentation and guidelines
- Python-based initialization tools

## Contributing

Please see the [CONTRIBUTING.md](.github/CONTRIBUTING.md) file for guidelines.