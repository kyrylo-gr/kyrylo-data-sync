# Microsoft's official Python dev container base image.
# It already includes a non-root 'vscode' user, git, sudo, and common build tools.
FROM mcr.microsoft.com/devcontainers/python:3.12

# Install any system packages your project needs.
# Add to this list — it stays inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

USER vscode
RUN curl -fsSL https://claude.ai/install.sh | bash