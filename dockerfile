# Use the official Miniconda3 image as base
FROM continuumio/miniconda3

# Set the working directory in the container
WORKDIR /app

# Copy the conda environment file into the container
COPY environment.yml .

# Create the conda environment from the environment file
RUN conda env create -n ytshorts -f environment.yml

# Ensure the conda environment’s bin directory is in the PATH
ENV PATH /opt/conda/envs/ytshorts/bin:$PATH

# Copy the application code into the container
COPY . .

# Expose port 8000 for the application
EXPOSE 8000

# Run the application with uvicorn; use "app:app" (module:application object)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "28080"]