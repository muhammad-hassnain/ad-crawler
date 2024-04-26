# Use Python 3.11 slim image based on Debian Buster as the base image
FROM python:3.11-slim-buster

# Set environment variables to ensure Python output is sent straight to the terminal without buffering
ENV PYTHONUNBUFFERED=1

# Create and set the working directory inside the container
WORKDIR /crawler

# Copy the requirements file into the container and install Python dependencies
COPY requirements.txt /crawler/
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# Install system dependencies for Xvfb, x11vnc, Fluxbox, DBus, and other necessary packages
# Add the Google Chrome installation in the same RUN command to avoid additional layers
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    fluxbox \
    dbus-x11 \
    wget \
    gnupg2 \
    ca-certificates \
    && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt install -y ./google-chrome-stable_current_amd64.deb \
    && rm ./google-chrome-stable_current_amd64.deb \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Avoid errors related to the display environment
ENV DISPLAY=:99

# Copy your application code, the `data` directory, and any other necessary files into the Docker image
COPY . /crawler/

# Expose the VNC port and the Flask app port
EXPOSE 1212 5000

# Set the PATH environment variable to include the directory where scripts are located
ENV PATH="/crawler:${PATH}"

# Set environment variable for the VNC password file path
ENV VNC_PASSWORD_FILE="/crawler/file"

# Set the VNC password
RUN x11vnc -storepasswd common456 $VNC_PASSWORD_FILE

# Modify the CMD to include the password file
CMD Xvfb :99 -screen 0 1024x768x16 & \
    dbus-launch fluxbox & \
    x11vnc -display :99 -N -forever -ncache_cr -rfbport 1212 -rfbauth $VNC_PASSWORD_FILE & \
    flask run --host=0.0.0.0 --port=5000 & \
    sleep 5 && \
    google-chrome --no-sandbox --disable-gpu --start-maximized "http://localhost:5000"

