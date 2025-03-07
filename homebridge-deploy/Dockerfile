# syntax = docker/dockerfile:1

# Adjust NODE_VERSION as desired
ARG NODE_VERSION=20.18.2
FROM node:${NODE_VERSION}-slim AS base

LABEL fly_launch_runtime="Node.js"

# Node.js app lives here
WORKDIR /app

# Set production environment
ENV NODE_ENV="production"

# Throw-away build stage to reduce size of final image
FROM base AS build

# Install packages needed to build node modules
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential node-gyp pkg-config python-is-python3

# Install Homebridge and Homebridge UI locally
RUN npm install --unsafe-perm homebridge homebridge-config-ui-x

# Install other node modules (optional based on your app)
COPY package-lock.json package.json ./
RUN npm ci

# Copy application code
COPY . .

# Final stage for app image
FROM base

# Create Homebridge config directory
RUN mkdir -p /app/.homebridge && chmod -R 777 /app/.homebridge

# Copy configuration file
COPY config.json /app/.homebridge/config.json

# Copy built application
COPY --from=build /app /app

# Expose ports
EXPOSE 51826 8581

# Start Homebridge
CMD [ "sh", "-c", "npx homebridge -I -U /app/.homebridge" ]