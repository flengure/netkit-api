# GitHub Actions Docker Hub Setup

The repository includes a GitHub Actions workflow that automatically builds and pushes Docker images to Docker Hub on every push to `main` or when version tags are created.

## Required Secrets

Add these secrets to your GitHub repository:

1. Go to: `https://github.com/flengure/netkit-api/settings/secrets/actions`

2. Add the following secrets:

### DOCKER_USERNAME
Your Docker Hub username: `flengure`

### DOCKER_PASSWORD
Docker Hub access token (recommended) or password:
- Go to https://hub.docker.com/settings/security
- Click "New Access Token"
- Name: `github-actions-netkit-api`
- Permissions: Read & Write
- Copy the token and add as secret

## Workflow Behavior

### On Push to Main
Builds and pushes:
- `flengure/netkit-api:main`
- `flengure/netkit-api:latest`

### On Version Tags (e.g., v2.1.0)
Builds and pushes:
- `flengure/netkit-api:2.1.0`
- `flengure/netkit-api:2.1`
- `flengure/netkit-api:2`
- `flengure/netkit-api:latest`

### Platform Support
Builds for:
- `linux/amd64` (x86_64)
- `linux/arm64` (ARM64/Apple Silicon)

## Manual Trigger

You can manually trigger a build:
1. Go to: `https://github.com/flengure/netkit-api/actions/workflows/docker-publish.yml`
2. Click "Run workflow"
3. Select branch
4. Click "Run workflow"

## Creating a Release

To publish a new version:

```bash
# Tag the release
git tag -a v2.1.0 -m "Release v2.1.0"
git push origin v2.1.0

# GitHub Actions will automatically:
# 1. Build multi-platform images
# 2. Push to Docker Hub with version tags
# 3. Update 'latest' tag
```

## Verifying the Build

After a successful workflow run:

```bash
# Check the image was pushed
docker pull flengure/netkit-api:latest

# Verify platforms
docker manifest inspect flengure/netkit-api:latest | grep -A 3 "platform"
```

## Troubleshooting

### Build Fails
- Check workflow logs in Actions tab
- Verify secrets are set correctly
- Ensure Dockerfile builds locally: `docker build -t test .`

### Push Fails
- Verify DOCKER_PASSWORD is an access token, not password
- Check token has Read & Write permissions
- Verify DOCKER_USERNAME is correct

### Multi-platform Build Fails
- This uses Docker Buildx
- Platforms: linux/amd64, linux/arm64
- If one platform fails, the entire build fails
