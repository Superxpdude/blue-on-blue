FROM docker.io/library/python:3.12-slim as debian

# Set the revision as an environment variable when building
ARG commit
ENV COMMIT=$commit

# Add opencontainers labels
LABEL org.opencontainers.image.source = "https://github.com/Superxpdude/blue-on-blue"
LABEL org.opencontainers.image.description = "A Discord bot for TMTM"

# Update installed packages and install tools for backups
RUN apt-get update && \
	apt-get upgrade -y && \
	apt-get install sqlite3 zip -y && \
	apt-get autoremove -y && \
	apt-get clean

# Select the working directory
WORKDIR /app

# Copy necessary files to the container
COPY ./src src
COPY ./pyproject.toml ./
COPY --chmod=755 ./scripts/container.sh ./entrypoint.sh
COPY --chmod=755 ./scripts/backup.sh /usr/local/bin/backup

# Create a python virtual environment
ENV VIRTUAL_ENV=/opt/venv
RUN python -m venv $VIRTUAL_ENV
# Add the venv to the front of the path so that it gets used
# by default for future python calls
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install python dependencies
RUN pip install -U pip
RUN pip install .

VOLUME ["/app/data"]

CMD ["start"]
ENTRYPOINT ["/app/entrypoint.sh"]
