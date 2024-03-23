# Start with a Python 3.11 slim image based on Debian Buster
FROM python:3.11-slim-buster


# Set an environment variable to ensure Python output is set straight
# to the terminal without buffering it first
ENV PYTHONUNBUFFERED=1


# Create and set the working directory inside the container
WORKDIR /crawler


# Copy the requirements file into the container and install Python dependencies
COPY requirements.txt /crawler/
RUN python -m pip install --upgrade pip && \
   pip install -r requirements.txt


# Install system dependencies required for a virtual display and Chrome
# This includes installing Xvfb, TigerVNC, and other necessary packages
RUN apt-get update && \
   apt-get install -y --no-install-recommends \
   xvfb \
   tigervnc-standalone-server \
   tigervnc-common \
   fluxbox \
   wget \
   gnupg2 \
   ca-certificates \
   && wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
   && apt install -y ./google-chrome-stable_current_amd64.deb \
   && rm ./google-chrome-stable_current_amd64.deb \
   && apt-get clean \
   && rm -rf /var/lib/apt/lists/*


# Copy your application code, the `data` directory, and any other necessary files into the Docker image
COPY . /crawler/


# Expose the VNC port, adjust if your setup uses a different port
EXPOSE 1212


# Set the PATH environment variable to include the directory where your scripts are located
ENV PATH="/crawler:${PATH}"


# Command to run when starting the container
CMD Xvfb :99 -screen 0 1024x768x16 & \
   DISPLAY=:99 \
   x11vnc -display :99 -N -forever -rfbport 1212 & \
   python3.11 ad-crawler.py -p "Test" -px "8022" -c "/crawler/chrome-profile" -mp "/crawler"
