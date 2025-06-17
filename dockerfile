# Use the official Miniconda3 image as base
FROM continuumio/miniconda3

# Set the working directory in the container
WORKDIR /app

# Copy the conda environment file into the container
COPY environment.yml .

# Create the conda environment from the environment file
RUN conda env create -n short_automation -f environment.yml

# Ensure the conda environment’s bin directory is in the PATH
ENV PATH /opt/conda/envs/short_automation/bin:$PATH

# Copy the application code into the container
COPY . .

# Install fonts for subtitles
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-dejavu \
        fonts-liberation && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Expose port 28080 for the application
EXPOSE 28080

# Run the application with uvicorn; use "app:app" (module:application object)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "28080"]
