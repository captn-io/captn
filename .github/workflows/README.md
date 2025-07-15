# GitHub Workflows

This directory contains GitHub Actions workflows for automated CI/CD processes.

## Docker Publishing Workflow

The `docker-publish.yml` workflow automatically builds and publishes Docker images to DockerHub.

### Features

- **Multi-platform builds**: Supports both `linux/amd64` and `linux/arm64` architectures
- **Automated tagging**: Creates semantic version tags, branch tags, and latest tags
- **Security scanning**: Integrates Trivy and Snyk for vulnerability scanning
- **Automated testing**: Pulls and tests the built image
- **Conditional publishing**: Only publishes on main branch pushes and releases, not on PRs

### Triggers

- Push to `main` branch
- Push of tags starting with `v*` (e.g., `v1.0.0`)
- Pull requests to `main` branch (build only, no publish)

### Required Secrets

Add these secrets to your GitHub repository settings:

1. **DOCKERHUB_USERNAME**: Your DockerHub username
2. **DOCKERHUB_TOKEN**: Your DockerHub access token (not your password)
3. **SNYK_TOKEN**: (Optional) Snyk API token for additional security scanning

### DockerHub Setup

1. Create a DockerHub account if you don't have one
2. Create a repository named `captn` under your organization/username
3. Generate an access token:
   - Go to DockerHub → Account Settings → Security
   - Click "New Access Token"
   - Give it a name like "GitHub Actions"
   - Copy the token and add it as `DOCKERHUB_TOKEN` secret

### Tagging Strategy

The workflow creates the following tags:

- `latest`: Latest build from main branch
- `dev`: Development build from main branch
- `v1.0.0`: Semantic version tags
- `1.0`: Major.minor version tags
- `1`: Major version tags
- `main`: Branch name tags

### Security Scanning

The workflow includes two security scanning tools:

1. **Trivy**: Scans for vulnerabilities and uploads results to GitHub Security tab
2. **Snyk**: Additional vulnerability scanning (requires SNYK_TOKEN secret)

### Manual Trigger

You can manually trigger the workflow:

1. Go to Actions tab in your GitHub repository
2. Select "CI deploy to Docker Hub"
3. Click "Run workflow"
4. Choose branch and click "Run workflow"

### Troubleshooting

- **Build failures**: Check Dockerfile syntax and dependencies
- **Authentication errors**: Verify DockerHub credentials in repository secrets
- **Permission errors**: Ensure the repository has proper permissions for packages and security events
- **Multi-platform build issues**: Verify Docker Buildx is properly configured

### Local Testing

To test the Docker build locally:

```bash
# Build the image
docker build -f docker/DOCKERFILE -t captn:test .

# Test the image
docker run --rm captn:test captn --help
``` 