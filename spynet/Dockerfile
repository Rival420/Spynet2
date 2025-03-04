# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Create the data directory for persistent storage
RUN mkdir -p /app/data

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project code into the container
COPY . .

# (Optional) If your front-end is built using create-react-app, you might have a build folder.
# You can also build it here if you include a package.json and the source files.
# For runtime configuration, we’ll assume you have a file "build/config.js.template"
# that we can substitute environment variables into.
COPY build/config.js.template ./build/config.js.template

# Expose port 5000 for the Flask app
EXPOSE 5000

# Copy the entrypoint script and mark it executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
