# Use the official Python 3.12 Debian-based image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

# Install nano, fish, and other necessary tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends nano fish binutils && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set fish as the default shell for the root user
RUN chsh -s /usr/bin/fish root

# Copy the requirements file and install dependencies
COPY source/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the pmctl.py script into the container
COPY source/pmctl.py /tmp/pmctl.py

# Install pyinstaller to build the binary
RUN pip install --no-cache-dir pyinstaller

# Build pmctl.py into a binary
RUN pyinstaller --onefile --name pmctl /tmp/pmctl.py

# Move the binary to /usr/local/bin and set permissions
RUN mv /dist/pmctl /usr/local/bin/pmctl && \
    chmod +x /usr/local/bin/pmctl

# Clean up unnecessary files
RUN rm -rf /tmp/* /dist /build

# Set the working directory
WORKDIR /app

# Set the default command to run fish shell
CMD ["fish"]